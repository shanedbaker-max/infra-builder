#!/usr/bin/env python3

import pandas as pd
from pathlib import Path

DOCS = Path("docs")

CRITICALITY = DOCS / "criticality_report.csv"
GRAPH = DOCS / "graph_criticality_report.csv"

MAP_FILE = "map_assets.html"

OUTPUT = DOCS / "dashboard.html"


def main():

    print("Loading analysis outputs...")

    crit_df = pd.read_csv(CRITICALITY)
    graph_df = pd.read_csv(GRAPH)

    crit_table = crit_df.to_html(index=False, classes="table", border=0)
    graph_table = graph_df.to_html(index=False, classes="table", border=0)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Infrastructure Resilience Analysis</title>

<style>
body {{
    font-family: Arial, sans-serif;
    margin: 40px;
    background: #f7f7f7;
}}

h1 {{
    margin-bottom: 10px;
}}

.table {{
    border-collapse: collapse;
    width: 100%;
}}

.table th, .table td {{
    border: 1px solid #ccc;
    padding: 8px;
}}

.table th {{
    background: #333;
    color: white;
}}

iframe {{
    border: none;
}}
</style>

</head>

<body>

<h1>Infrastructure Resilience Analysis</h1>

<p>
This dashboard shows infrastructure asset resilience based on simulated outage analysis.
Assets are ranked by network disruption impact.
</p>

<h2>Distance Model Critical Nodes</h2>

{crit_table}

<h2>Graph-Based Network Criticality</h2>

<p>
Graph analysis identifies nodes whose removal increases shortest-path distance or fragments the network.
</p>

{graph_table}

<h2>Infrastructure Map</h2>

<iframe src="{MAP_FILE}" width="100%" height="750"></iframe>

</body>
</html>
"""

    OUTPUT.write_text(html)

    print(f"Dashboard written to {OUTPUT}")


if __name__ == "__main__":
    main()