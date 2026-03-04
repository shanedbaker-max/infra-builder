#!/usr/bin/env python3
"""
critical_nodes.py

Rank infrastructure asset "criticality" by simulating an outage of each asset,
recomputing nearest-neighbor dependencies, and measuring the resulting distance impact.

Inputs:
- assets.geojson (FeatureCollection with Point geometries and properties including:
  asset_id, asset_type, lat, lon, city, status)

Outputs:
- criticality_report.csv (default) with columns:
  removed_asset_id, removed_asset_type, assets_impacted, total_delta_m, max_delta_m
"""

import argparse
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import pandas as pd
from geopy.distance import geodesic

ASSETS_FILE = "assets.geojson"
OUTPUT_FILE = "docs/criticality_report.csv"


def load_assets(path: str = ASSETS_FILE) -> gpd.GeoDataFrame:
    """
    Load assets from GeoJSON and ensure lat/lon columns are numeric.
    """
    gdf = gpd.read_file(path)

    # Normalize column presence
    required_cols = {"asset_id", "asset_type", "lat", "lon"}
    missing = required_cols - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    # Ensure numeric lat/lon
    gdf["lat"] = pd.to_numeric(gdf["lat"], errors="coerce")
    gdf["lon"] = pd.to_numeric(gdf["lon"], errors="coerce")

    # Drop any rows that still have invalid coords
    before = len(gdf)
    gdf = gdf.dropna(subset=["lat", "lon"]).copy()
    after = len(gdf)
    if after != before:
        print(f"Warning: dropped {before - after} assets with invalid lat/lon")

    return gdf


def compute_nearest_table(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each asset, compute its nearest other asset and distance (meters).

    Returns DataFrame with:
      asset_id, nearest_asset_id, nearest_distance_m
    """
    rows: List[Dict[str, object]] = []

    # Pre-extract for speed / clarity
    asset_ids = gdf["asset_id"].tolist()
    lats = gdf["lat"].tolist()
    lons = gdf["lon"].tolist()

    for i, asset_id in enumerate(asset_ids):
        p1 = (float(lats[i]), float(lons[i]))

        best_id: Optional[str] = None
        best_dist: Optional[float] = None

        for j, other_id in enumerate(asset_ids):
            if i == j:
                continue
            p2 = (float(lats[j]), float(lons[j]))
            d = geodesic(p1, p2).meters
            if best_dist is None or d < best_dist:
                best_dist = d
                best_id = other_id

        # If there's only 1 asset, best_dist stays None; handle gracefully
        rows.append(
            {
                "asset_id": asset_id,
                "nearest_asset_id": best_id,
                "nearest_distance_m": round(float(best_dist), 2) if best_dist is not None else 0.0,
            }
        )

    return pd.DataFrame(rows)


def simulate_outage_impact(gdf: gpd.GeoDataFrame, removed_asset_id: str) -> Dict[str, object]:
    """
    Remove one asset, recompute nearest-neighbor table for remaining assets,
    and compare against baseline to compute impact.

    Impact metrics:
      assets_impacted: number of assets whose nearest neighbor OR distance changed
      total_delta_m: sum of distance increases across impacted assets (meters)
      max_delta_m: max distance increase (meters)

    Notes:
      - If removal leaves 0 or 1 assets, impact will be zeros.
      - We consider changes where:
          nearest neighbor changed OR new distance > old distance
        (distance decrease is not counted as "impact" here; adjust if you want.)
    """
    if removed_asset_id not in set(gdf["asset_id"].values):
        raise ValueError(f"Asset not found: {removed_asset_id}")

    removed_type = gdf.loc[gdf["asset_id"] == removed_asset_id, "asset_type"].iloc[0]

    baseline = compute_nearest_table(gdf)

    post_gdf = gdf[gdf["asset_id"] != removed_asset_id].copy()
    if len(post_gdf) <= 1:
        return {
            "removed_asset_id": removed_asset_id,
            "removed_asset_type": removed_type,
            "assets_impacted": 0,
            "total_delta_m": 0.0,
            "max_delta_m": 0.0,
        }

    post = compute_nearest_table(post_gdf)

    merged = baseline.merge(
        post,
        on="asset_id",
        how="inner",
        suffixes=("_old", "_new"),
    )

    impacted = 0
    deltas: List[float] = []

    for _, row in merged.iterrows():
        old_nearest = row["nearest_asset_id_old"]
        new_nearest = row["nearest_asset_id_new"]
        old_dist = float(row["nearest_distance_m_old"])
        new_dist = float(row["nearest_distance_m_new"])

        # If the removed asset is the one being evaluated, it won't be in merged (since post removed it)
        # So no need to special-case.

        delta = new_dist - old_dist
        changed = (old_nearest != new_nearest) or (delta > 0)

        if changed:
            impacted += 1
            if delta > 0:
                deltas.append(delta)
            else:
                # nearest changed but distance did not increase; count as impacted with 0 delta
                deltas.append(0.0)

    total_delta = round(sum(deltas), 2) if deltas else 0.0
    max_delta = round(max(deltas), 2) if deltas else 0.0

    return {
        "removed_asset_id": removed_asset_id,
        "removed_asset_type": removed_type,
        "assets_impacted": impacted,
        "total_delta_m": total_delta,
        "max_delta_m": max_delta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank asset criticality by outage impact")
    parser.add_argument("--top", type=int, default=10, help="Show top N most critical nodes")
    parser.add_argument("--out", type=str, default=OUTPUT_FILE, help="Output CSV filename")
    parser.add_argument("--assets", type=str, default=ASSETS_FILE, help="Input assets GeoJSON filename")
    args = parser.parse_args()

    print("Loading assets...")
    gdf = load_assets(args.assets)

    print(f"Assets loaded: {len(gdf)}")
    print("Computing criticality (simulate outage for each asset)...\n")

    results: List[Dict[str, object]] = []
    for asset_id in gdf["asset_id"].tolist():
        impact = simulate_outage_impact(gdf, asset_id)
        results.append(impact)

    df = pd.DataFrame(results).sort_values("total_delta_m", ascending=False)

    print("Top Critical Nodes:\n")
    print(df.head(args.top).to_string(index=False))

    df.to_csv(args.out, index=False)
    print(f"\nFull report written to: {args.out}")


if __name__ == "__main__":
    main()