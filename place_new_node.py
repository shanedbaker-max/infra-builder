#!/usr/bin/env python3
"""
place_new_node.py

Spatial "new node placement" optimizer.

Goal:
- Propose candidate locations for a NEW infrastructure node (e.g., a new tower),
  connect it to nearby nodes (k-nearest), and evaluate resilience improvement
  via Monte Carlo simulation (same concept as your existing simulator).

Inputs:
- assets.geojson (must include: asset_id, asset_type, lat, lon)

Outputs:
- docs/node_placement_recs.csv (default)

Notes:
- This is intentionally simple + deterministic.
- It avoids AWS entirely. Runs local only.
"""

import argparse
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import geopandas as gpd
import pandas as pd
import networkx as nx

ASSETS_FILE = "assets.geojson"


# ----------------------------
# Geometry / distance helpers
# ----------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (meters)."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def load_assets(path: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)

    req = {"asset_id", "asset_type", "lat", "lon"}
    missing = req - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    gdf["lat"] = pd.to_numeric(gdf["lat"], errors="coerce")
    gdf["lon"] = pd.to_numeric(gdf["lon"], errors="coerce")
    gdf = gdf.dropna(subset=["lat", "lon"]).copy()

    return gdf


# ----------------------------
# Graph construction
# ----------------------------

def build_knn_graph(gdf: gpd.GeoDataFrame, k: int) -> nx.Graph:
    """
    Build an undirected k-nearest-neighbor graph by geo distance.
    Edge weight = distance meters.
    """
    G = nx.Graph()

    rows = gdf[["asset_id", "asset_type", "lat", "lon"]].to_dict("records")
    for r in rows:
        G.add_node(r["asset_id"], **r)

    # For each node, connect to k nearest other nodes
    for i, a in enumerate(rows):
        dists: List[Tuple[float, str]] = []
        for j, b in enumerate(rows):
            if i == j:
                continue
            d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
            dists.append((d, b["asset_id"]))
        dists.sort(key=lambda x: x[0])
        for d, bid in dists[: max(1, k)]:
            # undirected; add_edge handles duplicates
            G.add_edge(a["asset_id"], bid, weight=float(d))

    return G


# ----------------------------
# Monte Carlo resilience
# ----------------------------

@dataclass
class MCResult:
    mean_components: float
    mean_lcc_ratio: float


def monte_carlo_resilience(G: nx.Graph, fail_prob: float, trials: int, seed: int = 7) -> MCResult:
    """
    Node failure Monte Carlo:
    - Each trial removes each node independently with probability fail_prob
    - Measure: number of connected components
    - Measure: largest connected component ratio
    """
    rng = random.Random(seed)

    nodes = list(G.nodes())
    n_total = len(nodes)
    if n_total == 0:
        return MCResult(0.0, 0.0)

    comps_sum = 0.0
    lcc_sum = 0.0

    for _ in range(trials):
        alive = [n for n in nodes if rng.random() > fail_prob]
        if len(alive) == 0:
            comps = 0
            lcc_ratio = 0.0
        else:
            H = G.subgraph(alive).copy()
            comps = nx.number_connected_components(H)
            largest = max((len(c) for c in nx.connected_components(H)), default=0)
            lcc_ratio = largest / float(len(alive)) if len(alive) else 0.0

        comps_sum += comps
        lcc_sum += lcc_ratio

    return MCResult(
        mean_components=round(comps_sum / trials, 4),
        mean_lcc_ratio=round(lcc_sum / trials, 4),
    )


# NOTE: keep random import down here so it’s obvious it’s used by MC
import random


# ----------------------------
# Candidate generation
# ----------------------------

def make_candidate_grid(gdf: gpd.GeoDataFrame, grid_n: int, pad_frac: float = 0.05) -> List[Tuple[float, float]]:
    """
    Create a simple lat/lon grid over the asset bounding box.
    """
    min_lat = float(gdf["lat"].min())
    max_lat = float(gdf["lat"].max())
    min_lon = float(gdf["lon"].min())
    max_lon = float(gdf["lon"].max())

    lat_pad = (max_lat - min_lat) * pad_frac
    lon_pad = (max_lon - min_lon) * pad_frac

    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    if grid_n < 2:
        grid_n = 2

    lats = [min_lat + i * (max_lat - min_lat) / (grid_n - 1) for i in range(grid_n)]
    lons = [min_lon + j * (max_lon - min_lon) / (grid_n - 1) for j in range(grid_n)]

    candidates = [(lat, lon) for lat in lats for lon in lons]
    return candidates


def attach_new_node(G: nx.Graph, new_id: str, lat: float, lon: float, k_attach: int) -> nx.Graph:
    """
    Return a COPY of graph with a new node connected to its k nearest existing nodes.
    """
    H = G.copy()
    H.add_node(new_id, asset_id=new_id, asset_type="candidate_node", lat=lat, lon=lon)

    existing = [n for n in H.nodes() if n != new_id]
    dists: List[Tuple[float, str]] = []
    for n in existing:
        nlat = float(H.nodes[n].get("lat"))
        nlon = float(H.nodes[n].get("lon"))
        d = haversine_m(lat, lon, nlat, nlon)
        dists.append((d, n))
    dists.sort(key=lambda x: x[0])

    for d, n in dists[: max(1, k_attach)]:
        H.add_edge(new_id, n, weight=float(d))

    return H


# ----------------------------
# Main optimization
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Recommend best new node locations via Monte Carlo resilience")
    ap.add_argument("--assets", default=ASSETS_FILE, help="Input GeoJSON filename")
    ap.add_argument("--k", type=int, default=2, help="k-nearest connectivity for base graph")
    ap.add_argument("--k-attach", type=int, default=2, help="How many neighbors the NEW node attaches to")
    ap.add_argument("--fail-prob", type=float, default=0.15, help="Node failure probability per trial")
    ap.add_argument("--trials", type=int, default=500, help="Monte Carlo trials per candidate")
    ap.add_argument("--grid-n", type=int, default=8, help="Grid size per axis (total candidates = grid_n^2)")
    ap.add_argument("--top", type=int, default=10, help="Top N candidate placements to print")
    ap.add_argument("--out", default="docs/node_placement_recs.csv", help="Output CSV path")
    args = ap.parse_args()

    print("Loading assets...")
    gdf = load_assets(args.assets)
    print(f"Assets loaded: {len(gdf)}")

    print(f"Building base graph (k={args.k})...")
    G = build_knn_graph(gdf, k=args.k)
    print(f"Graph nodes: {G.number_of_nodes()}  edges: {G.number_of_edges()}")

    print("Running baseline Monte Carlo...")
    base = monte_carlo_resilience(G, fail_prob=args.fail_prob, trials=args.trials, seed=7)
    print(f"Baseline mean_components={base.mean_components}  mean_lcc_ratio={base.mean_lcc_ratio}")

    print(f"Generating candidate grid (grid_n={args.grid_n})...")
    candidates = make_candidate_grid(gdf, grid_n=args.grid_n)

    results: List[Dict[str, object]] = []
    print(f"Evaluating {len(candidates)} candidates...")

    for idx, (clat, clon) in enumerate(candidates):
        new_id = f"NEW_{idx:03d}"
        H = attach_new_node(G, new_id=new_id, lat=clat, lon=clon, k_attach=args.k_attach)
        mc = monte_carlo_resilience(H, fail_prob=args.fail_prob, trials=args.trials, seed=7)

        # Score: prefer fewer components AND higher LCC ratio.
        # Convert both into "improvement" vs baseline.
        delta_components = base.mean_components - mc.mean_components          # positive is good
        delta_lcc = mc.mean_lcc_ratio - base.mean_lcc_ratio                  # positive is good

        # Weighted score (simple + explainable)
        score = (delta_components * 1.0) + (delta_lcc * 1.0)

        results.append(
            {
                "candidate_id": new_id,
                "candidate_lat": round(float(clat), 6),
                "candidate_lon": round(float(clon), 6),
                "base_mean_components": base.mean_components,
                "base_mean_lcc_ratio": base.mean_lcc_ratio,
                "new_mean_components": mc.mean_components,
                "new_mean_lcc_ratio": mc.mean_lcc_ratio,
                "delta_components": round(float(delta_components), 4),
                "delta_lcc_ratio": round(float(delta_lcc), 4),
                "score": round(float(score), 6),
            }
        )

    df = pd.DataFrame(results).sort_values("score", ascending=False)

    print("\nTop New Node Placement Recommendations (SIMULATED):\n")
    print(df.head(args.top)[
        ["candidate_id", "candidate_lat", "candidate_lon", "delta_components", "delta_lcc_ratio", "score"]
    ].to_string(index=False))

    # Ensure output directory exists
    out_path = args.out
    out_dir = "/".join(out_path.split("/")[:-1])
    if out_dir:
        import os
        os.makedirs(out_dir, exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()