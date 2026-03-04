#!/usr/bin/env python3
"""
monte_carlo_resilience.py

Monte Carlo network resilience simulation for infrastructure assets.

Reads:
- assets.geojson

Builds a network graph (NetworkX) using either:
- K-nearest neighbors edges (default), optionally limited by radius_m.

Simulates random outage scenarios and measures:
- components (fragmentation)
- largest component ratio
- average shortest path length (within largest component)
- connectivity status

Writes:
- docs/monte_carlo_summary.csv
- docs/monte_carlo_node_risk.csv
- (optional) docs/monte_carlo_runs.csv

Usage:
  ./gis_env/bin/python monte_carlo_resilience.py --iters 5000 --p 0.15 --k 2
"""

import argparse
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import networkx as nx
import pandas as pd
from geopy.distance import geodesic

ASSETS_FILE = "assets.geojson"
OUT_DIR = Path("docs")

SUMMARY_CSV = OUT_DIR / "monte_carlo_summary.csv"
NODE_RISK_CSV = OUT_DIR / "monte_carlo_node_risk.csv"
RUNS_CSV = OUT_DIR / "monte_carlo_runs.csv"


@dataclass
class RunMetrics:
    run_id: int
    failed_count: int
    components: int
    largest_component_ratio: float
    avg_shortest_path_m: float
    is_connected: int  # 1/0


def load_assets(path: str = ASSETS_FILE) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)

    required = {"asset_id", "asset_type", "lat", "lon"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    gdf["lat"] = pd.to_numeric(gdf["lat"], errors="coerce")
    gdf["lon"] = pd.to_numeric(gdf["lon"], errors="coerce")

    before = len(gdf)
    gdf = gdf.dropna(subset=["lat", "lon"]).copy()
    after = len(gdf)
    if after != before:
        print(f"Warning: dropped {before - after} rows with invalid lat/lon")

    return gdf


def geodesic_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return float(geodesic((lat1, lon1), (lat2, lon2)).meters)


def build_graph(
    gdf: gpd.GeoDataFrame,
    k: int = 2,
    radius_m: Optional[float] = None,
) -> nx.Graph:
    """
    Build an undirected weighted graph.

    Strategy:
      - For each node, connect to its k nearest neighbors by geodesic distance.
      - If radius_m is set, only keep edges <= radius_m (may fragment the graph).
    """
    G = nx.Graph()

    # Add nodes
    for _, row in gdf.iterrows():
        G.add_node(
            row["asset_id"],
            asset_type=row["asset_type"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
        )

    ids = gdf["asset_id"].tolist()
    lats = gdf["lat"].astype(float).tolist()
    lons = gdf["lon"].astype(float).tolist()

    # Add edges (k nearest per node)
    for i, a_id in enumerate(ids):
        dists: List[Tuple[float, str]] = []
        for j, b_id in enumerate(ids):
            if i == j:
                continue
            d = geodesic_m(lats[i], lons[i], lats[j], lons[j])
            dists.append((d, b_id))

        dists.sort(key=lambda x: x[0])
        for d, b_id in dists[: max(1, k)]:
            if radius_m is not None and d > radius_m:
                continue
            # Avoid duplicate edges automatically in nx.Graph
            G.add_edge(a_id, b_id, weight_m=float(d))

    return G


def induced_subgraph_without_nodes(G: nx.Graph, failed_nodes: List[str]) -> nx.Graph:
    keep = [n for n in G.nodes() if n not in set(failed_nodes)]
    return G.subgraph(keep).copy()


def avg_shortest_path_in_largest_component(G: nx.Graph) -> float:
    """
    Average weighted shortest path length within the largest connected component.
    Returns 0.0 if component size < 2.
    """
    if G.number_of_nodes() < 2:
        return 0.0
    if G.number_of_edges() == 0:
        return 0.0

    components = list(nx.connected_components(G))
    if not components:
        return 0.0

    largest = max(components, key=len)
    H = G.subgraph(largest).copy()
    if H.number_of_nodes() < 2 or H.number_of_edges() == 0:
        return 0.0

    # NetworkX avg_shortest_path_length requires connectivity; H is connected
    try:
        return float(nx.average_shortest_path_length(H, weight="weight_m"))
    except Exception:
        return 0.0


def run_monte_carlo(
    G: nx.Graph,
    iters: int,
    p_fail: float,
    min_fail: int = 1,
    max_fail: Optional[int] = None,
    seed: Optional[int] = None,
    write_runs: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Returns:
      summary_df: overall summary (single-row)
      node_risk_df: per-node risk contributions
      runs_df: optional per-run metrics
    """
    if seed is not None:
        random.seed(seed)

    nodes = list(G.nodes())
    n_total = len(nodes)
    if n_total < 2:
        raise ValueError("Need at least 2 nodes for meaningful Monte Carlo simulation.")

    if not (0.0 < p_fail < 1.0):
        raise ValueError("--p must be between 0 and 1 (exclusive).")

    # Baseline (no failure) reference
    base_components = nx.number_connected_components(G) if n_total > 0 else 0
    base_is_connected = 1 if nx.is_connected(G) else 0
    base_avg_sp = avg_shortest_path_in_largest_component(G)
    base_largest_ratio = (
        len(max(nx.connected_components(G), key=len)) / n_total if n_total > 0 else 0.0
    )

    # Track node “badness”: how often a node is involved in runs with severe degradation
    node_failure_count = {n: 0 for n in nodes}
    node_severe_count = {n: 0 for n in nodes}

    runs: List[RunMetrics] = []

    # Define what "severe" means (tweakable)
    # Severe if largest component drops below 0.75 of original OR components increases by >= 1
    severe_largest_ratio_threshold = 0.75

    for r in range(1, iters + 1):
        # sample failures
        # expected failures is ~ p_fail * n_total, but we clamp to [min_fail, max_fail]
        sampled = [n for n in nodes if random.random() < p_fail]
        if len(sampled) < min_fail:
            sampled = random.sample(nodes, k=min_fail)
        if max_fail is not None and len(sampled) > max_fail:
            sampled = random.sample(sampled, k=max_fail)

        for n in sampled:
            node_failure_count[n] += 1

        H = induced_subgraph_without_nodes(G, sampled)
        n_remain = H.number_of_nodes()
        if n_remain == 0:
            comps = 0
            largest_ratio = 0.0
            avg_sp = 0.0
            connected = 0
        else:
            comps = nx.number_connected_components(H)
            largest_ratio = len(max(nx.connected_components(H), key=len)) / n_total
            avg_sp = avg_shortest_path_in_largest_component(H)
            connected = 1 if (H.number_of_nodes() > 0 and nx.is_connected(H)) else 0

        severe = (largest_ratio < severe_largest_ratio_threshold) or (comps > base_components)

        if severe:
            for n in sampled:
                node_severe_count[n] += 1

        runs.append(
            RunMetrics(
                run_id=r,
                failed_count=len(sampled),
                components=int(comps),
                largest_component_ratio=round(float(largest_ratio), 4),
                avg_shortest_path_m=round(float(avg_sp), 2),
                is_connected=int(connected),
            )
        )

    runs_df = pd.DataFrame([r.__dict__ for r in runs])

    # Summary
    summary = {
        "assets_total": n_total,
        "iters": iters,
        "p_fail": p_fail,
        "baseline_components": base_components,
        "baseline_is_connected": base_is_connected,
        "baseline_largest_component_ratio": round(float(base_largest_ratio), 4),
        "baseline_avg_shortest_path_m": round(float(base_avg_sp), 2),
        "mean_failed_count": round(float(runs_df["failed_count"].mean()), 2),
        "mean_components": round(float(runs_df["components"].mean()), 2),
        "p_connected": round(float(runs_df["is_connected"].mean()), 4),
        "mean_largest_component_ratio": round(float(runs_df["largest_component_ratio"].mean()), 4),
        "p_largest_component_ratio_lt_0_75": round(
            float((runs_df["largest_component_ratio"] < 0.75).mean()), 4
        ),
        "mean_avg_shortest_path_m": round(float(runs_df["avg_shortest_path_m"].mean()), 2),
    }
    summary_df = pd.DataFrame([summary])

    # Per-node risk
    node_rows = []
    for n in nodes:
        fails = node_failure_count[n]
        severe = node_severe_count[n]
        node_rows.append(
            {
                "asset_id": n,
                "asset_type": G.nodes[n].get("asset_type"),
                "failed_in_runs": fails,
                "failed_rate": round(fails / iters, 4),
                "severe_when_failed_runs": severe,
                "severe_when_failed_rate": round((severe / fails), 4) if fails else 0.0,
                "severity_score": round((severe / iters), 4),  # simple overall “badness”
            }
        )
    node_risk_df = pd.DataFrame(node_rows).sort_values(
        ["severity_score", "failed_rate"], ascending=False
    )

    return summary_df, node_risk_df, (runs_df if write_runs else None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monte Carlo network resilience simulation")
    parser.add_argument("--assets", default=ASSETS_FILE, help="Input GeoJSON")
    parser.add_argument("--iters", type=int, default=5000, help="Number of Monte Carlo runs")
    parser.add_argument("--p", type=float, default=0.15, help="Failure probability per node per run (0-1)")
    parser.add_argument("--k", type=int, default=2, help="K nearest neighbors per node in graph")
    parser.add_argument("--radius-m", type=float, default=None, help="Optional max edge distance in meters")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--min-fail", type=int, default=1, help="Minimum nodes to fail per run")
    parser.add_argument("--max-fail", type=int, default=None, help="Maximum nodes to fail per run")
    parser.add_argument("--write-runs", action="store_true", help="Write per-run metrics CSV")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading assets...")
    gdf = load_assets(args.assets)
    print(f"Assets loaded: {len(gdf)}")

    print("Building graph...")
    G = build_graph(gdf, k=args.k, radius_m=args.radius_m)
    print(f"Graph nodes: {G.number_of_nodes()} edges: {G.number_of_edges()}")

    print("Running Monte Carlo...")
    summary_df, node_risk_df, runs_df = run_monte_carlo(
        G=G,
        iters=args.iters,
        p_fail=args.p,
        min_fail=args.min_fail,
        max_fail=args.max_fail,
        seed=args.seed,
        write_runs=args.write_runs,
    )

    summary_df.to_csv(SUMMARY_CSV, index=False)
    node_risk_df.to_csv(NODE_RISK_CSV, index=False)
    if runs_df is not None:
        runs_df.to_csv(RUNS_CSV, index=False)

    print(f"\nWrote: {SUMMARY_CSV}")
    print(f"Wrote: {NODE_RISK_CSV}")
    if runs_df is not None:
        print(f"Wrote: {RUNS_CSV}")

    print("\nMonte Carlo summary:")
    print(summary_df.to_string(index=False))

    print("\nTop node risk (severity_score):")
    print(node_risk_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()