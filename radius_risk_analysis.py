import geopandas as gpd

INPUT_FILE = "assets.geojson"
RISK_RADIUS_M = 5000  # 5 km


def main():

    print("Loading spatial dataset...")
    gdf = gpd.read_file(INPUT_FILE)

    print(f"Assets loaded: {len(gdf)}")

    # convert to projected CRS so distances are meters
    gdf = gdf.to_crs(epsg=3857)

    print(f"\nAssets within {RISK_RADIUS_M/1000} km risk radius:\n")

    for i, asset in gdf.iterrows():

        for j, other in gdf.iloc[i+1:].iterrows():

            if i == j:
                continue

            distance = asset.geometry.distance(other.geometry)

            if distance <= RISK_RADIUS_M:

                print(
                    f"{asset['asset_type']} {asset['asset_id']} "
                    f"→ within {round(distance,2)} m of "
                    f"{other['asset_type']} {other['asset_id']}"
                )


if __name__ == "__main__":
    main()