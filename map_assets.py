#!/usr/bin/env python3
"""
map_assets.py

Creates an interactive HTML map from assets.geojson and overlays:
- Asset markers colored by risk_score (from risk_report.csv)
- Optional nearest-neighbor "link" lines (from risk_report.csv nearest_asset_id)
- Optional radius circles (meters) (from risk_report.csv radius_m)

Run (recommended):
  ./gis_env/bin/python map_assets.py

Outputs:
  map_assets.html
"""

from __future__ import annotations

import os
from typing import Optional

import geopandas as gpd
import pandas as pd
import folium


# ---- Config ----
GEOJSON_FILE = os.getenv("GEOJSON_FILE", "assets.geojson")
RISK_REPORT_FILE = os.getenv("RISK_REPORT_FILE", "risk_report.csv")
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "map_assets.html")

# If true, draw line from each asset -> its nearest neighbor (using nearest_asset_id)
DRAW_NEAREST_LINKS = os.getenv("DRAW_NEAREST_LINKS", "true").strip().lower() in {"1", "true", "yes", "y"}

# If true, draw radius circles for each asset (using radius_m)
DRAW_RADIUS = os.getenv("DRAW_RADIUS", "true").strip().lower() in {"1", "true", "yes", "y"}


def risk_color(score: Optional[float]) -> str:
    """
    Match your risk scoring semantics:
      >= 3  -> green (good redundancy)
      >= 1  -> orange (moderate)
      else  -> red (isolated/vulnerable)
    """
    if score is None or pd.isna(score):
        return "gray"
    try:
        s = float(score)
    except Exception:
        return "gray"

    if s >= 3:
        return "green"
    if s >= 1:
        return "orange"
    return "red"


def pick_map_center(gdf: gpd.GeoDataFrame) -> tuple[float, float]:
    """Return (lat, lon) center for map initialization."""
    # Use centroid of bounds (works fine for small extents like your sample)
    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy) in lon/lat for EPSG:4326
    minx, miny, maxx, maxy = bounds
    center_lon = (minx + maxx) / 2.0
    center_lat = (miny + maxy) / 2.0
    return center_lat, center_lon


def main() -> None:
    if not os.path.exists(GEOJSON_FILE):
        raise FileNotFoundError(f"Missing {GEOJSON_FILE}. Run export_geojson.py first.")

    if not os.path.exists(RISK_REPORT_FILE):
        raise FileNotFoundError(f"Missing {RISK_REPORT_FILE}. Run risk_summary.py first to generate it.")

    # --- Load spatial data ---
    gdf = gpd.read_file(GEOJSON_FILE)

    # Ensure we have lon/lat points
    if gdf.crs is None:
        # Your GeoJSON includes CRS84; if missing, assume WGS84
        gdf.set_crs("EPSG:4326", inplace=True)
    else:
        # Normalize to EPSG:4326 for folium
        gdf = gdf.to_crs("EPSG:4326")

    # --- Load risk report + merge ---
    risk = pd.read_csv(RISK_REPORT_FILE)

    # Expected columns from your risk_report.csv:
    # asset_id, asset_type, risk_score, nearest_asset_id, nearest_asset_type, nearest_distance_m, radius_m
    required_cols = {"asset_id", "risk_score"}
    missing = required_cols - set(risk.columns)
    if missing:
        raise ValueError(f"{RISK_REPORT_FILE} is missing columns: {sorted(missing)}")

    # Merge on asset_id
    gdf = gdf.merge(risk, on="asset_id", how="left", suffixes=("", "_risk"))

    # --- Build map ---
    center_lat, center_lon = pick_map_center(gdf)
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, control_scale=True, tiles="OpenStreetMap")

    # Index for nearest lookup by asset_id
    # We'll use lat/lon from gdf geometry for line drawing.
    by_id = {}
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        # geom is Point(lon, lat) for EPSG:4326
        by_id[row["asset_id"]] = (float(geom.y), float(geom.x))

    # Feature groups for toggles
    fg_assets = folium.FeatureGroup(name="Assets (risk colored)", show=True)
    fg_links = folium.FeatureGroup(name="Nearest links", show=True)
    fg_radius = folium.FeatureGroup(name="Risk radius", show=True)

    # --- Add markers / overlays ---
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue

        lat = float(geom.y)
        lon = float(geom.x)

        asset_id = str(row.get("asset_id", "UNKNOWN"))
        asset_type = str(row.get("asset_type", "unknown"))
        city = str(row.get("city", ""))

        score = row.get("risk_score", None)
        nearest_id = row.get("nearest_asset_id", None)
        nearest_dist_m = row.get("nearest_distance_m", None)
        radius_m = row.get("radius_m", None)

        color = risk_color(score)

        # Popup text (keep it clean and useful)
        popup_lines = [
            f"<b>{asset_type}</b> ({asset_id})",
        ]
        if city:
            popup_lines.append(f"City: {city}")
        if score is not None and not pd.isna(score):
            popup_lines.append(f"Risk score: {float(score):.2f}")
        else:
            popup_lines.append("Risk score: N/A")

        if nearest_id is not None and not pd.isna(nearest_id):
            popup_lines.append(f"Nearest: {nearest_id}")
        if nearest_dist_m is not None and not pd.isna(nearest_dist_m):
            popup_lines.append(f"Nearest dist: {float(nearest_dist_m):.2f} m")
        if radius_m is not None and not pd.isna(radius_m):
            popup_lines.append(f"Radius: {float(radius_m):.0f} m")

        popup_html = "<br/>".join(popup_lines)

        # Marker
        folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            color=color,
            fill=True,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{asset_type} {asset_id} (score={score if score is not None else 'N/A'})",
        ).add_to(fg_assets)

        # Optional radius circle
        if DRAW_RADIUS and radius_m is not None and not pd.isna(radius_m):
            try:
                r = float(radius_m)
                if r > 0:
                    folium.Circle(
                        location=[lat, lon],
                        radius=r,
                        color=color,
                        weight=2,
                        fill=False,
                        opacity=0.45,
                    ).add_to(fg_radius)
            except Exception:
                pass

        # Optional nearest link
        if DRAW_NEAREST_LINKS and nearest_id is not None and not pd.isna(nearest_id):
            nid = str(nearest_id)
            if nid in by_id:
                nlat, nlon = by_id[nid]
                folium.PolyLine(
                    locations=[[lat, lon], [nlat, nlon]],
                    color="black",
                    weight=2,
                    opacity=0.6,
                ).add_to(fg_links)

    # Add layers
    fg_assets.add_to(m)
    if DRAW_NEAREST_LINKS:
        fg_links.add_to(m)
    if DRAW_RADIUS:
        fg_radius.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Save
    m.save(OUTPUT_HTML)
    print(f"Map created: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()