#!/usr/bin/env python3
"""
optimize_infrastructure.py

(SIMULATED) Network optimization module: recommend NEW REDUNDANT LINKS (edges)
that improve Monte Carlo resilience metrics.

Inputs:
- assets.geojson with Point features and properties: asset_id, asset_type, lat, lon

Outputs:
- CSV recommendations: best new edges to add (u, v) and estimated resilience gain

Notes:
- This does NOT add new nodes yet (that’s Step 2).
- It evaluates candidate edges within a max distance threshold and ranks by improvement.
"""

import argparse
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import geopandas as gpd
import pandas as pd
import networkx as nx
from geopy.distance import geodesic


ASSETS_FILE = "assets.geojson"


@dataclass
class ResilienceResult:
    mean_components: float
    mean_lcc_ratio: float
    score: float


def load_assets(path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)

    required = {"asset_id", "asset_type", "lat", "lon"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    gdf["lat"] = pd.to_numeric(gdf["lat"], errors="coerce")
    gdf["lon"] = pd.to_numeric(gdf["lon"], errors="coerce")
    gdf = gdf.dropna(subset=["lat", "lon"]).copy()

    # Make sure asset_id is string-ish
    gdf["asset_id"] = gdf["asset_id"].astype(str)

    return gdf


def build_knn_graph(gdf: gpd.GeoDataFrame, k: int) -> nx.Graph:
    """
    Build an undirected k-nearest neighbor graph using geodesic distance as edge weight (meters).
    """
    if k < 1:
        raise ValueError("k must be >= 1")

    nodes = gdf["asset_id"].tolist()
    coords = {row["asset_id"]: (float(row["lat"]), float(row["lon"])) for _, row in gdf.iterrows()}

    G = nx.Graph()
    for n in nodes:
        G.add_node(n)

    for n in nodes:
        # compute distances to all others
        dists = []
        for m in nodes:
            if n == m:
                continue
            d = geodesic(coords[n], coords[m]).meters
            dists.append((m, d))
        dists.sort(key=lambda x: x[1])

        # connect to k nearest
        for m, d in dists[:k]:
            if not G.has_edge(n, m):
                G.add_edge(n, m, weight=float(d))

    return G


def simulate_failures_metrics(G: nx.Graph, p_fail: float, trials: int, seed: int) -> ResilienceResult:
    """
    Monte Carlo: each node independently fails with prob p_fail.
    Compute:
      - mean number of connected components among surviving nodes
      - mean largest connected component ratio (LCC size / surviving nodes)
    Then compute a combined score (higher = better).

    Score heuristic (tweakable):
      score = mean_lcc_ratio - 0.25 * (mean_components - 1)/(max_components)
    """
    if not (0.0 <= p_fail <= 1.0):
        raise ValueError("p_fail must be between 0 and 1")
    if trials < 1:
        raise ValueError("trials must be >= 1")

    rnd = random.Random(seed)

    nodes = list(G.nodes())
    n = len(nodes)
    if n == 0:
        return ResilienceResult(0.0, 0.0, 0.0)

    comps_list: List[int] = []
    lcc_ratio_list: List[float] = []

    for _ in range(trials):
        surviving = [u for u in nodes if rnd.random() > p_fail]

        if len(surviving) <= 1:
            # 0 or 1 surviving nodes => 0 components by “network” meaning, LCC ratio is 1 for 1 node, else 0
            comps = 0 if len(surviving) == 0 else 1
            lcc_ratio = 0.0 if len(surviving) == 0 else 1.0
            comps_list.append(comps)
            lcc_ratio_list.append(lcc_ratio)
            continue

        H = G.subgraph(surviving)
        comps = nx.number_connected_components(H)
        largest = max((len(c) for c in nx.connected_components(H)), default=0)
        lcc_ratio = largest / len(surviving)

        comps_list.append(comps)
        lcc_ratio_list.append(lcc_ratio)

    mean_components = sum(comps_list) / len(comps_list)
    mean_lcc_ratio = sum(lcc_ratio_list) / len(lcc_ratio_list)

    # Normalize component penalty (max possible components ~ surviving nodes)
    # Use n-1 as “max fragmentation” scale
    max_scale = max(n - 1, 1)
    penalty = 0.25 * max(0.0, (mean_components - 1.0) / max_scale)

    score = mean_lcc_ratio - penalty

    return ResilienceResult(
        mean_components=round(mean_components, 4),
        mean_lcc_ratio=round(mean_lcc_ratio, 4),
        score=round(score, 6),
    )


def candidate_edges_by_distance(gdf: gpd.GeoDataFrame, G: nx.Graph, max_m: float, limit: int) -> List[Tuple[str, str, float]]:
    """
    Build candidate NEW edges between currently unconnected node pairs within max distance.
    Returns list of (u, v, distance_m), sorted by distance ascending.
    """
    coords = {row["asset_id"]: (float(row["lat"]), float(row["lon"])) for _, row in gdf.iterrows()}
    nodes = list(G.nodes())

    cand: List[Tuple[str, str, float]] = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            u, v = nodes[i], nodes[j]
            if G.has_edge(u, v):
                continue
            d = geodesic(coords[u], coords[v]).meters
            if d <= max_m:
                cand.append((u, v, float(d)))

    cand.sort(key=lambda x: x[2])
    if limit and len(cand) > limit:
        cand = cand[:limit]
    return cand


def evaluate_edge_additions(
    gdf: gpd.GeoDataFrame,
    base_G: nx.Graph,
    candidates: List[Tuple[str, str, float]],
    p_fail: float,
    trials: int,
    seed: int,
) -> pd.DataFrame:
    """
    For each candidate edge (u, v), add it (with weight=distance),
    simulate failures, and compute improvement vs baseline.
    """
    baseline = simulate_failures_metrics(base_G, p_fail=p_fail, trials=trials, seed=seed)

    rows: List[Dict[str, object]] = []
    for u, v, d in candidates:
        G2 = base_G.copy()
        G2.add_edge(u, v, weight=float(d))

        r2 = simulate_failures_metrics(G2, p_fail=p_fail, trials=trials, seed=seed)

        rows.append(
            {
                "recommendation": f"Add redundant link {u} <-> {v}",
                "u": u,
                "v": v,
                "distance_m": round(d, 2),
                "baseline_score": baseline.score,
                "new_score": r2.score,
                "score_gain": round(r2.score - baseline.score, 6),
                "baseline_mean_components": baseline.mean_components,
                "new_mean_components": r2.mean_components,
                "baseline_lcc_ratio": baseline.mean_lcc_ratio,
                "new_lcc_ratio": r2.mean_lcc_ratio,
            }
        )

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df
    df = df.sort_values(["score_gain", "new_score"], ascending=[False, False]).reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend network redundancy improvements (SIMULATED)")
    parser.add_argument("--assets", default=ASSETS_FILE, help="Input assets GeoJSON")
    parser.add_argument("--k", type=int, default=2, help="k-nearest connectivity for base graph")
    parser.add_argument("--failure-prob", type=float, default=0.15, help="Node failure probability per trial")
    parser.add_argument("--trials", type=int, default=500, help="Monte Carlo trials per evaluation")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--candidate-max-m", type=float, default=8000.0, help="Max distance for candidate new links (meters)")
    parser.add_argument("--candidate-limit", type=int, default=50, help="Limit number of candidates evaluated (closest pairs)")
    parser.add_argument("--top", type=int, default=10, help="Print top N recommendations")
    parser.add_argument("--out", default="docs/optimization_recs.csv", help="Output CSV file")
    args = parser.parse_args()

    print("Loading assets...")
    gdf = load_assets(args.assets)
    print(f"Assets loaded: {len(gdf)}")

    print(f"Building base graph (k={args.k})...")
    G = build_knn_graph(gdf, k=args.k)
    print(f"Graph nodes: {G.number_of_nodes()}  edges: {G.number_of_edges()}")

    print("Generating candidate redundancy links...")
    candidates = candidate_edges_by_distance(gdf, G, max_m=args.candidate_max_m, limit=args.candidate_limit)
    print(f"Candidates evaluated: {len(candidates)} (max_m={args.candidate_max_m}, limit={args.candidate_limit})")

    if not candidates:
        print("No candidate edges found. Try raising --candidate-max-m or lowering k.")
        return

    print("Evaluating candidate links via Monte Carlo...")
    df = evaluate_edge_additions(
        gdf=gdf,
        base_G=G,
        candidates=candidates,
        p_fail=args.failure_prob,
        trials=args.trials,
        seed=args.seed,
    )

    if df.empty:
        print("No results.")
        return

    # Print top recommendations
    print("\nTop Recommendations (SIMULATED):\n")
    print(df.head(args.top)[["recommendation", "distance_m", "score_gain", "new_score", "new_mean_components", "new_lcc_ratio"]].to_string(index=False))

    # Save
    out_path = args.out
    # ensure parent dir exists (lightweight)
    import os
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()