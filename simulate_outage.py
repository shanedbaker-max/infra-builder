import argparse
import geopandas as gpd
import pandas as pd

from geopy.distance import geodesic


ASSETS_FILE = "assets.geojson"
OUTPUT_FILE = "simulated_risk_report.csv"


def load_assets(path: str = ASSETS_FILE) -> gpd.GeoDataFrame:
    print("Loading assets...")
    gdf = gpd.read_file(path)

    required = {"asset_id", "asset_type", "lat", "lon"}
    missing = required - set(gdf.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

    return gdf


def simulate_removal(gdf: gpd.GeoDataFrame, asset_id: str):
    print(f"\nSimulating outage for asset: {asset_id}")

    if asset_id not in set(gdf["asset_id"].astype(str).values):
        raise ValueError(f"Asset not found: {asset_id}")

    removed = gdf[gdf["asset_id"].astype(str) == str(asset_id)].copy()
    remaining = gdf[gdf["asset_id"].astype(str) != str(asset_id)].copy()

    return removed, remaining


def nearest_neighbors(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each asset, find the nearest other asset using geodesic distance.
    Returns: asset_id, nearest_asset_id, nearest_distance_m
    """
    rows = []

    # If only 0/1 assets, there's no nearest neighbor computation to do.
    if len(gdf) < 2:
        for _, r in gdf.iterrows():
            rows.append(
                {
                    "asset_id": str(r["asset_id"]),
                    "asset_type": r["asset_type"],
                    "nearest_asset_id": None,
                    "nearest_distance_m": None,
                }
            )
        return pd.DataFrame(rows)

    for _, row in gdf.iterrows():
        min_dist = None
        nearest_id = None

        p1 = (float(row["lat"]), float(row["lon"]))
        row_id = str(row["asset_id"])

        for _, other in gdf.iterrows():
            other_id = str(other["asset_id"])
            if row_id == other_id:
                continue

            p2 = (float(other["lat"]), float(other["lon"]))
            dist = geodesic(p1, p2).meters

            if (min_dist is None) or (dist < min_dist):
                min_dist = dist
                nearest_id = other_id

        rows.append(
            {
                "asset_id": row_id,
                "asset_type": row["asset_type"],
                "nearest_asset_id": nearest_id,
                "nearest_distance_m": round(min_dist, 2) if min_dist is not None else None,
            }
        )

    return pd.DataFrame(rows)


def build_outage_delta_report(
    baseline: pd.DataFrame,
    after: pd.DataFrame,
    removed_asset_id: str,
    removed_asset_type: str,
) -> pd.DataFrame:
    """
    Create an executive-readable delta report with before/after nearest neighbor changes.

    Output columns:
      asset_id, asset_type,
      old_nearest_asset_id, old_nearest_distance_m,
      new_nearest_asset_id, new_nearest_distance_m,
      delta_m,
      removed_asset_id, removed_asset_type
    """
    baseline = baseline.copy()
    after = after.copy()

    # Normalize dtypes
    baseline["asset_id"] = baseline["asset_id"].astype(str)
    after["asset_id"] = after["asset_id"].astype(str)

    merged = baseline.merge(after, on=["asset_id", "asset_type"], how="inner", suffixes=("_old", "_new"))

    merged = merged.rename(
        columns={
            "nearest_asset_id_old": "old_nearest_asset_id",
            "nearest_distance_m_old": "old_nearest_distance_m",
            "nearest_asset_id_new": "new_nearest_asset_id",
            "nearest_distance_m_new": "new_nearest_distance_m",
        }
    )

    merged["delta_m"] = (merged["new_nearest_distance_m"] - merged["old_nearest_distance_m"]).round(2)

    merged["removed_asset_id"] = str(removed_asset_id)
    merged["removed_asset_type"] = removed_asset_type

    # Make it easy to scan: biggest negative/positive deltas first.
    merged = merged.sort_values(by="delta_m", ascending=False)

    cols = [
        "asset_id",
        "asset_type",
        "old_nearest_asset_id",
        "old_nearest_distance_m",
        "new_nearest_asset_id",
        "new_nearest_distance_m",
        "delta_m",
        "removed_asset_id",
        "removed_asset_type",
    ]
    return merged[cols]


def print_executive_summary(delta_df: pd.DataFrame, removed_id: str, removed_type: str) -> None:
    print("\n--- Outage Impact Summary ---")
    print(f"Removed: {removed_id} ({removed_type})")
    print(f"Assets evaluated: {len(delta_df)}")

    if len(delta_df) == 0:
        print("No remaining assets to evaluate.")
        return

    changed = delta_df[
        (delta_df["old_nearest_asset_id"] != delta_df["new_nearest_asset_id"])
        | (delta_df["delta_m"].abs() > 0.0)
    ]
    print(f"Assets with changed dependency or distance: {len(changed)}")

    # Top impacts (largest distance increase)
    top = delta_df.sort_values("delta_m", ascending=False).head(5)
    print("\nTop 5 distance increases (meters):")
    for _, r in top.iterrows():
        print(
            f"- {r['asset_id']} ({r['asset_type']}): "
            f"{r['old_nearest_asset_id']} @ {r['old_nearest_distance_m']}m -> "
            f"{r['new_nearest_asset_id']} @ {r['new_nearest_distance_m']}m "
            f"(Δ {r['delta_m']}m)"
        )


def main():
    parser = argparse.ArgumentParser(description="Simulate an infrastructure node outage and recompute nearest-neighbor dependencies.")
    parser.add_argument("--asset", required=True, help="Asset ID to remove (simulate outage)")

    args = parser.parse_args()

    gdf = load_assets()

    # Baseline dependencies (with all assets)
    baseline_df = nearest_neighbors(gdf)

    removed, remaining = simulate_removal(gdf, args.asset)
    removed_id = str(removed.iloc[0]["asset_id"])
    removed_type = str(removed.iloc[0]["asset_type"])

    print(f"Removed asset:\n{removed[['asset_id','asset_type']]}")

    print("\nRecomputing dependencies (post-outage)...\n")
    after_df = nearest_neighbors(remaining)

    delta_df = build_outage_delta_report(
        baseline=baseline_df[baseline_df["asset_id"] != removed_id],  # removed asset can't be evaluated after removal
        after=after_df,
        removed_asset_id=removed_id,
        removed_asset_type=removed_type,
    )

    # Print a compact table + summary
    print(delta_df.to_string(index=False))

    delta_df.to_csv(OUTPUT_FILE, index=False)
    print_executive_summary(delta_df, removed_id, removed_type)

    print("\nSimulation complete.")
    print(f"Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()