#!/usr/bin/env python3
"""
build_dashboard.py

Build a simple HTML dashboard that combines:
- Critical nodes ranking table (from a CSV)
- Embedded interactive Folium map (map_assets.html)

Expected inputs:
- docs/criticality_report.csv
- docs/map_assets.html   (or map_assets.html, depending on your workflow)

Output:
- docs/dashboard.html
"""

from pathlib import Path
import pandas as pd

DOCS_DIR = Path("docs")
CRIT_CSV = DOCS_DIR / "criticality_report.csv"
MAP_HTML = DOCS_DIR / "map_assets.html"
OUT_HTML = DOCS_DIR / "dashboard.html"


def load_table_html(csv_path: Path) -> str:
    df = pd.read_csv(csv_path)

    # Format numeric columns nicely if present
    for col in ["total_delta_m", "max_delta_m"]:
        if col in df.columns:
            df[col] = df[col].map(lambda x: f"{float(x):.2f}")

    # Build HTML table
    return df.to_html(index=False, classes="data-table", border=0)


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if not CRIT_CSV.exists():
        raise FileNotFoundError(f"Missing required file: {CRIT_CSV}")

    # Prefer docs/map_assets.html. If not present, fall back to root map_assets.html
    map_src = "./map_assets.html"
    if MAP_HTML.exists():
        map_src = "./map_assets.html"  # relative to docs/dashboard.html
    else:
        fallback = Path("map_assets.html")
        if fallback.exists():
            # If you keep the map at repo root, this path works from docs/dashboard.html
            map_src = "../map_assets.html"
        else:
            # Still generate dashboard (table-only) but warn visually
            map_src = None

    table_html = load_table_html(CRIT_CSV)

    map_block = ""
    if map_src:
        map_block = f"""
        <h2>Infrastructure Map</h2>
        <iframe src="{map_src}" width="100%" height="750" style="border:1px solid #ddd; border-radius: 8px;"></iframe>
        """
    else:
        map_block = """
        <h2>Infrastructure Map</h2>
        <div class="warn">
            map_assets.html not found. Expected at <code>docs/map_assets.html</code> or <code>map_assets.html</code>.
            Run <code>./gis_env/bin/python map_assets.py</code> and ensure it writes the file into <code>docs/</code>.
        </div>
        """

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Infrastructure Resilience Analysis</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 40px;
      color: #111;
    }}
    h1 {{
      margin-bottom: 6px;
    }}
    .subtitle {{
      color: #444;
      max-width: 980px;
      line-height: 1.4;
      margin-bottom: 28px;
    }}
    .data-table {{
      border-collapse: collapse;
      width: 100%;
      max-width: 1200px;
      margin-bottom: 28px;
    }}
    .data-table thead th {{
      background: #222;
      color: #fff;
      text-align: left;
      padding: 10px 12px;
      font-weight: 600;
      border: 1px solid #444;
    }}
    .data-table tbody td {{
      padding: 10px 12px;
      border: 1px solid #ccc;
    }}
    .warn {{
      padding: 14px 16px;
      background: #fff3cd;
      border: 1px solid #ffeeba;
      border-radius: 8px;
      max-width: 980px;
    }}
    code {{
      background: #f5f5f5;
      padding: 2px 6px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <h1>Infrastructure Resilience Analysis</h1>
  <div class="subtitle">
    This dashboard shows infrastructure asset resilience based on simulated outage analysis.
    Assets are ranked by total distance impact when removed from the network.
  </div>

  <h2>Critical Nodes Ranking</h2>
  {table_html}

  {map_block}
</body>
</html>
"""

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard: {OUT_HTML}")


if __name__ == "__main__":
    main()