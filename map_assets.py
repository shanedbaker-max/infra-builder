#!/usr/bin/env python3
"""
map_assets.py

Build an interactive infrastructure map (Folium) with:
- Assets (colored by risk if risk_report.csv exists)
- Nearest-neighbor links (optional)
- Risk radius rings (optional)
- Recommended build sites from node placement optimization (optional)

Inputs:
- assets.geojson
- (optional) risk_report.csv
- (optional) docs/node_placement_recs.csv

Output:
- map_assets.html
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import geopandas as gpd
import pandas as pd
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import MarkerCluster
from geopy.distance import geodesic


ASSETS_FILE = "assets.geojson"
RISK_REPORT_FILE = "risk_report.csv"                  # optional
NODE_PLACEMENT_FILE = "docs/node_placement_recs.csv"  # optional (your new placements)
OUTPUT_HTML = "map_assets.html"

DEFAULT_RADIUS_M = 5000  # used if you want to visualize risk radius rings


# -------------------------
# Helpers
# -------------------------
def safe_float(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


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
    if len(gdf) != before:
        print(f"Warning: dropped {before - len(gdf)} assets with invalid lat/lon")

    return gdf


def load_risk_scores(path: str = RISK_REPORT_FILE) -> Optional[pd.DataFrame]:
    p = Path(path)
    if not p.exists():
        return None

    df = pd.read_csv(p)
    # Expect at minimum asset_id and something risk-related. Your repo has risk_report.csv from risk_summary.py.
    if "asset_id" not in df.columns:
        return None

    # Normalize a single "risk_score" column if possible.
    # If your risk_report already contains risk_score, use it.
    if "risk_score" in df.columns:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce").fillna(0.0)
        return df[["asset_id", "risk_score"]]

    # If not present, try to derive from distance metrics.
    # Prefer nearest_distance_m if available.
    for candidate in ["nearest_distance_m", "distance_m", "nearest_distance"]:
        if candidate in df.columns:
            s = pd.to_numeric(df[candidate], errors="coerce").fillna(0.0)
            # Normalize to 0..1-ish (avoid divide by zero)
            denom = max(s.max(), 1.0)
            df["risk_score"] = (s / denom).clip(0, 1)
            return df[["asset_id", "risk_score"]]

    # Nothing usable found
    return None


def risk_color(score: float) -> str:
    """
    Map risk score [0..1] to a color.
    """
    score = max(0.0, min(1.0, float(score)))
    if score >= 0.66:
        return "red"
    if score >= 0.33:
        return "orange"
    return "green"


def compute_nearest_neighbor(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Return table: asset_id, nearest_asset_id, nearest_distance_m
    """
    rows: List[Dict[str, object]] = []

    asset_ids = gdf["asset_id"].tolist()
    lats = gdf["lat"].tolist()
    lons = gdf["lon"].tolist()

    for i, aid in enumerate(asset_ids):
        p1 = (float(lats[i]), float(lons[i]))
        best_id = None
        best_dist = None

        for j, oid in enumerate(asset_ids):
            if i == j:
                continue
            p2 = (float(lats[j]), float(lons[j]))
            d = geodesic(p1, p2).meters
            if best_dist is None or d < best_dist:
                best_dist = d
                best_id = oid

        rows.append(
            {
                "asset_id": aid,
                "nearest_asset_id": best_id,
                "nearest_distance_m": round(float(best_dist), 2) if best_dist is not None else 0.0,
            }
        )

    return pd.DataFrame(rows)


def load_node_placements(path: str = NODE_PLACEMENT_FILE) -> Optional[pd.DataFrame]:
    p = Path(path)
    if not p.exists():
        return None

    df = pd.read_csv(p)

    required = {"candidate_id", "candidate_lat", "candidate_lon"}
    missing = required - set(df.columns)
    if missing:
        print(f"Found {path} but missing columns: {sorted(missing)}")
        return None

    df["candidate_lat"] = pd.to_numeric(df["candidate_lat"], errors="coerce")
    df["candidate_lon"] = pd.to_numeric(df["candidate_lon"], errors="coerce")
    df = df.dropna(subset=["candidate_lat", "candidate_lon"]).copy()

    # Optional columns your script prints/writes:
    # delta_components, delta_lcc_ratio, score
    for c in ["delta_components", "delta_lcc_ratio", "score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def add_fit_bounds(m: folium.Map, points: List[Tuple[float, float]]) -> None:
    """
    Fit map bounds to points (lat, lon).
    """
    if not points:
        return

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    south_west = (min(lats), min(lons))
    north_east = (max(lats), max(lons))
    m.fit_bounds([south_west, north_east])


# -------------------------
# Main map build
# -------------------------
def main():
    print("Loading assets...")
    gdf = load_assets(ASSETS_FILE)
    print(f"Assets loaded: {len(gdf)}")

    risk_df = load_risk_scores(RISK_REPORT_FILE)
    risk_map = {}
    if risk_df is not None:
        risk_map = dict(zip(risk_df["asset_id"], risk_df["risk_score"]))
        print(f"Loaded risk scores for {len(risk_map)} assets from {RISK_REPORT_FILE}")
    else:
        print(f"No usable risk scores found (missing/invalid {RISK_REPORT_FILE}). Using neutral styling.")

    nn_df = compute_nearest_neighbor(gdf)

    node_df = load_node_placements(NODE_PLACEMENT_FILE)
    # Only show top N recommendations on the map
    TOP_RECOMMENDATIONS = 5

    if node_df is not None:
     node_df = node_df.sort_values("score", ascending=False).head(TOP_RECOMMENDATIONS)
    if node_df is not None and len(node_df) > 0:
        print(f"Loaded {len(node_df)} recommended build sites from {NODE_PLACEMENT_FILE}")
    else:
        print(f"No recommended build sites found at {NODE_PLACEMENT_FILE} (skipping layer).")
        node_df = None

    # Initial map center = centroid-ish of assets (fallback)
    center_lat = float(gdf["lat"].mean())
    center_lon = float(gdf["lon"].mean())
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="openstreetmap")

    # Layers
    assets_layer = FeatureGroup(name="Assets (risk colored)", show=True)
    links_layer = FeatureGroup(name="Nearest links", show=True)
    radius_layer = FeatureGroup(name="Risk radius", show=True)
    recs_layer = FeatureGroup(name="Recommended build sites", show=True)

    # Cluster for assets (nice UX)
    asset_cluster = MarkerCluster(name="Asset cluster", control=False)  # cluster inside assets layer

    # Add assets
    all_points: List[Tuple[float, float]] = []

    for _, row in gdf.iterrows():
        aid = str(row["asset_id"])
        atype = str(row["asset_type"])
        lat = float(row["lat"])
        lon = float(row["lon"])
        all_points.append((lat, lon))

        score = float(risk_map.get(aid, 0.0))
        color = risk_color(score) if risk_df is not None else "blue"

        popup_html = f"""
        <b>{aid}</b><br/>
        type: {atype}<br/>
        lat/lon: {lat:.5f}, {lon:.5f}<br/>
        risk_score: {score:.3f}
        """

        folium.CircleMarker(
            location=(lat, lon),
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{aid} ({atype})",
        ).add_to(asset_cluster)

        # Risk radius ring (toggle)
        folium.Circle(
            location=(lat, lon),
            radius=DEFAULT_RADIUS_M,
            color=color,
            weight=2,
            opacity=0.4,
            fill=False,
        ).add_to(radius_layer)

    asset_cluster.add_to(assets_layer)

    # Nearest links
    # draw simple polylines asset -> nearest_asset
    coord_lookup = {str(r["asset_id"]): (float(r["lat"]), float(r["lon"])) for _, r in gdf.iterrows()}

    for _, r in nn_df.iterrows():
        a = str(r["asset_id"])
        b = r["nearest_asset_id"]
        if b is None or (isinstance(b, float) and math.isnan(b)):
            continue
        b = str(b)
        if a not in coord_lookup or b not in coord_lookup:
            continue

        (lat1, lon1) = coord_lookup[a]
        (lat2, lon2) = coord_lookup[b]
        d = float(r["nearest_distance_m"])

        folium.PolyLine(
            locations=[(lat1, lon1), (lat2, lon2)],
            weight=3,
            opacity=0.7,
            tooltip=f"{a} → {b}: {d:.2f} m",
        ).add_to(links_layer)

    # Recommended build sites layer
    if node_df is not None and len(node_df) > 0:
        for _, r in node_df.iterrows():
            cid = str(r["candidate_id"])
            lat = float(r["candidate_lat"])
            lon = float(r["candidate_lon"])
            all_points.append((lat, lon))

            delta_components = r["delta_components"] if "delta_components" in node_df.columns else None
            delta_lcc_ratio = r["delta_lcc_ratio"] if "delta_lcc_ratio" in node_df.columns else None
            score = r["score"] if "score" in node_df.columns else None

            lines = [f"<b>{cid}</b>", "Recommended build site"]
            lines.append(f"lat/lon: {lat:.5f}, {lon:.5f}")
            if delta_components is not None and not pd.isna(delta_components):
                lines.append(f"Δ components: {float(delta_components):.3f}")
            if delta_lcc_ratio is not None and not pd.isna(delta_lcc_ratio):
                lines.append(f"Δ LCC ratio: {float(delta_lcc_ratio):.4f}")
            if score is not None and not pd.isna(score):
                lines.append(f"score: {float(score):.4f}")

            popup_html = "<br/>".join(lines)

            folium.Marker(
                location=(lat, lon),
                tooltip=f"{cid} (recommended)",
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color="blue", icon="plus", prefix="fa"),
            ).add_to(recs_layer)

    # Add layers
    assets_layer.add_to(m)
    links_layer.add_to(m)
    radius_layer.add_to(m)
    if node_df is not None and len(node_df) > 0:
        recs_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # Fit map to all points (assets + recs)
    add_fit_bounds(m, all_points)

    m.save(OUTPUT_HTML)
    print(f"Map created: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()