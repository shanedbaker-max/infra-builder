import streamlit as st
import pandas as pd
import networkx as nx
import random
import geopandas as gpd
from geopy.distance import geodesic

st.title("Infrastructure Digital Twin Simulator")

ASSETS_FILE = "assets.geojson"

@st.cache_data
def load_assets():
    gdf = gpd.read_file(ASSETS_FILE)
    return gdf

def geodesic_m(a,b,c,d):
    return geodesic((a,b),(c,d)).meters

def build_graph(gdf,k=2):

    G = nx.Graph()

    for _,row in gdf.iterrows():
        G.add_node(row["asset_id"],
                   lat=row["lat"],
                   lon=row["lon"],
                   asset_type=row["asset_type"])

    ids = gdf["asset_id"].tolist()

    for i,row in gdf.iterrows():

        dists = []

        for j,row2 in gdf.iterrows():
            if i==j:
                continue

            d = geodesic_m(row.lat,row.lon,row2.lat,row2.lon)

            dists.append((d,row2.asset_id))

        dists.sort()

        for d,n in dists[:k]:
            G.add_edge(row.asset_id,n,weight=d)

    return G

gdf = load_assets()

st.write(f"Assets loaded: {len(gdf)}")

k = st.slider("Graph connectivity (k nearest)",1,5,2)

G = build_graph(gdf,k)

st.write(f"Graph nodes: {G.number_of_nodes()}")
st.write(f"Graph edges: {G.number_of_edges()}")

p_fail = st.slider("Node failure probability",0.01,0.5,0.15)

runs = st.slider("Simulations per batch",50,1000,200)

start = st.button("Run Simulation")

if start:

    nodes = list(G.nodes())

    severe_count = {n:0 for n in nodes}

    results = []

    for r in range(runs):

        failed = [n for n in nodes if random.random()<p_fail]

        if len(failed)==0:
            failed = random.sample(nodes,1)

        H = G.copy()
        H.remove_nodes_from(failed)

        if H.number_of_nodes()==0:
            largest_ratio = 0
            components = 0
        else:
            components = nx.number_connected_components(H)
            largest = max(nx.connected_components(H),key=len)
            largest_ratio = len(largest)/len(nodes)

        severe = largest_ratio < 0.75

        if severe:
            for n in failed:
                severe_count[n]+=1

        results.append({
            "failed_nodes":len(failed),
            "components":components,
            "largest_ratio":largest_ratio
        })

    df = pd.DataFrame(results)

    st.subheader("Simulation Results")

    st.metric("Mean components",round(df.components.mean(),2))
    st.metric("Mean largest component ratio",round(df.largest_ratio.mean(),2))

    risk = pd.DataFrame({
        "asset_id":list(severe_count.keys()),
        "risk_score":[severe_count[n]/runs for n in severe_count]
    })

    risk = risk.sort_values("risk_score",ascending=False)

    st.subheader("Top Risk Nodes")

    st.dataframe(risk)