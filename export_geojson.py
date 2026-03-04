import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

INPUT_FILE = "assets_clean.csv"
OUTPUT_FILE = "assets.geojson"


def main():
    print("Loading cleaned assets...")

    df = pd.read_csv(INPUT_FILE)

    print(f"Rows loaded: {len(df)}")

    geometry = [Point(xy) for xy in zip(df["lon"], df["lat"])]

    gdf = gpd.GeoDataFrame(df, geometry=geometry)

    gdf.set_crs(epsg=4326, inplace=True)

    print("Exporting GeoJSON...")

    gdf.to_file(OUTPUT_FILE, driver="GeoJSON")

    print(f"GIS layer created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()