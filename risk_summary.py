import csv
import math
from typing import Dict, List, Tuple

import geopandas as gpd


INPUT_GEOJSON = "assets.geojson"
OUTPUT_CSV = "risk_report.csv"

# Radius for "neighbors within X meters"
RADIUS_M = 5000.0

# We'll project to meters for distance math
METRIC_EPSG = 3857


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Fallback distance (meters) if you ever need it without projections.
    Not used when we have GeoPandas + projected CRS, but kept as a safe utility.
    """
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_assets() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(INPUT_GEOJSON)

    required = {"asset_id", "asset_type", "geometry"}
    missing = required - set(gdf.columns)
    if missing:
        raise RuntimeError(f"GeoJSON missing required columns: {sorted(missing)}")

    # Ensure CRS known; your GeoJSON shows EPSG:4326 already, but guard anyway
    if gdf.crs is None:
        # assume WGS84 if missing
        gdf = gdf.set_crs(epsg=4326)

    # Project to meters for distance calculations
    gdf_m = gdf.to_crs(epsg=METRIC_EPSG)

    # Keep a copy of lat/lon if you want them in output later
    # (Not required for this report.)
    return gdf_m


def compute_nearest_and_radius(gdf_m: gpd.GeoDataFrame) -> List[Dict]:
    """
    For each asset:
      - find nearest other asset (by geometry distance)
      - count how many other assets are within RADIUS_M
    """
    rows: List[Dict] = []

    # Pre-pull for speed/readability
    ids = list(gdf_m["asset_id"])
    types = list(gdf_m["asset_type"])
    geoms = list(gdf_m.geometry)

    n = len(gdf_m)
    if n < 2:
        raise RuntimeError("Need at least 2 assets to compute nearest neighbor.")

    for i in range(n):
        asset_id = ids[i]
        asset_type = types[i]
        geom_i = geoms[i]

        nearest_id = None
        nearest_type = None
        nearest_dist = None

        within_count = 0

        for j in range(n):
            if i == j:
                continue

            d = geom_i.distance(geoms[j])  # meters (because EPSG:3857)
            if d <= RADIUS_M:
                within_count += 1

            if nearest_dist is None or d < nearest_dist:
                nearest_dist = d
                nearest_id = ids[j]
                nearest_type = types[j]

        rows.append(
            {
                "asset_id": asset_id,
                "asset_type": asset_type,
                "risk_score": within_count,  # how many neighbors within radius
                "nearest_asset_id": nearest_id,
                "nearest_asset_type": nearest_type,
                "nearest_distance_m": round(float(nearest_dist), 2) if nearest_dist is not None else None,
                "radius_m": int(RADIUS_M),
            }
        )

    return rows


def write_csv(rows: List[Dict]) -> None:
    fieldnames = [
        "asset_id",
        "asset_type",
        "risk_score",
        "nearest_asset_id",
        "nearest_asset_type",
        "nearest_distance_m",
        "radius_m",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    gdf_m = load_assets()
    rows = compute_nearest_and_radius(gdf_m)
    # Sort: highest risk_score first, then nearest distance ascending
    rows.sort(key=lambda r: (-r["risk_score"], r["nearest_distance_m"]))
    write_csv(rows)

    print(f"Wrote: {OUTPUT_CSV}")
    print(f"Assets analyzed: {len(rows)}")
    print(f"Radius used: {int(RADIUS_M)} m")


if __name__ == "__main__":
    main()