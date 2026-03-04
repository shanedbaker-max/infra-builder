#!/usr/bin/env python3

import geopandas as gpd
import pandas as pd
import networkx as nx
from geopy.distance import geodesic

ASSETS_FILE = "assets.geojson"
OUTPUT_FILE = "docs/graph_criticality_report.csv"


def load_assets():
    print("Loading assets...")
    gdf = gpd.read_file(ASSETS_FILE)

    gdf["lat"] = pd.to_numeric(gdf["lat"], errors="coerce")
    gdf["lon"] = pd.to_numeric(gdf["lon"], errors="coerce")

    gdf = gdf.dropna(subset=["lat", "lon"])

    return gdf


def distance(a, b):
    p1 = (a["lat"], a["lon"])
    p2 = (b["lat"], b["lon"])
    return geodesic(p1, p2).meters


def build_graph(gdf, k=3):
    print("Building network graph...")

    G = nx.Graph()

    for _, row in gdf.iterrows():
        G.add_node(
            row["asset_id"],
            asset_type=row["asset_type"],
            lat=row["lat"],
            lon=row["lon"],
        )

    for i, a in gdf.iterrows():

        dists = []

        for j, b in gdf.iterrows():
            if a["asset_id"] == b["asset_id"]:
                continue

            d = distance(a, b)
            dists.append((b["asset_id"], d))

        dists.sort(key=lambda x: x[1])

        for neighbor, dist in dists[:k]:
            G.add_edge(a["asset_id"], neighbor, weight=dist)

    return G


def graph_metrics(G):

    betweenness = nx.betweenness_centrality(G, weight="weight")
    articulation = set(nx.articulation_points(G))

    return betweenness, articulation


def simulate_node_removal(G):

    print("Simulating node failures...")

    baseline_paths = dict(nx.all_pairs_dijkstra_path_length(G, weight="weight"))

    results = []

    for node in G.nodes():

        H = G.copy()
        H.remove_node(node)

        impacted = 0
        delta_total = 0
        delta_max = 0

        try:
            new_paths = dict(nx.all_pairs_dijkstra_path_length(H, weight="weight"))
        except:
            new_paths = {}

        for a in baseline_paths:

            if a == node:
                continue

            for b in baseline_paths[a]:

                if b == node or a == b:
                    continue

                old = baseline_paths[a][b]

                try:
                    new = new_paths[a][b]
                except:
                    new = float("inf")

                if new > old:
                    impacted += 1

                    delta = new - old
                    if delta != float("inf"):
                        delta_total += delta
                        delta_max = max(delta_max, delta)

        results.append(
            {
                "removed_asset_id": node,
                "assets_impacted": impacted,
                "total_delta_m": round(delta_total, 2),
                "max_delta_m": round(delta_max, 2),
            }
        )

    return pd.DataFrame(results)


def main():

    gdf = load_assets()

    print(f"Assets loaded: {len(gdf)}")

    G = build_graph(gdf)

    betweenness, articulation = graph_metrics(G)

    print("\nArticulation points (network break risk):")
    for n in articulation:
        print(n)

    results = simulate_node_removal(G)

    results["betweenness"] = results["removed_asset_id"].map(betweenness)

    results = results.sort_values("total_delta_m", ascending=False)

    results.to_csv(OUTPUT_FILE, index=False)

    print("\nTop Graph Critical Nodes:\n")
    print(results.head(10))

    print(f"\nReport written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()