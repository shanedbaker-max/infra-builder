import geopandas as gpd

INPUT_FILE = "assets.geojson"

def main():

    print("Loading spatial dataset...")
    gdf = gpd.read_file(INPUT_FILE)

    print(f"Assets loaded: {len(gdf)}")

    # Convert to metric projection for distance calculations
    gdf = gdf.to_crs(epsg=3857)

    print("\nNearest asset for each infrastructure node:\n")

    for i, asset in gdf.iterrows():

        nearest_distance = None
        nearest_asset_id = None
        nearest_asset_type = None

        for j, other in gdf.iterrows():

            if i == j:
                continue

            distance = asset.geometry.distance(other.geometry)

            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_asset_id = other["asset_id"]
                nearest_asset_type = other["asset_type"]

        print(
            f"{asset['asset_type']} {asset['asset_id']} → nearest: "
            f"{nearest_asset_type} {nearest_asset_id} "
            f"({round(nearest_distance,2)} m)"
        )


if __name__ == "__main__":
    main()