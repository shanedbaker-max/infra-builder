# Infra Builder – Week 01

Small Python pipeline that:

1. Cleans asset CSV data
2. Classifies infrastructure risk
3. Uploads results to AWS S3
4. Downloads and verifies integrity

## Setup

Create virtual environment

python -m venv venv
source venv/bin/activate

Install dependencies

pip install -r requirements.txt

Configure AWS

aws configure
aws sts get-caller-identity

Create environment config

cp .env.example .env

Edit `.env` and set your bucket.

## Run Pipeline

Clean data

python clean_assets.py

Upload to S3

python s3_upload.py

Download and verify

python s3_download_verify.py

## Infrastructure Spatial Analysis

This project also includes a geospatial infrastructure analysis layer built using GeoPandas.

### GeoJSON Conversion
Asset data is converted into a spatial dataset:

## Failure Simulation

The project includes an infrastructure outage simulator.

Example:

python simulate_outage.py --asset A002

This removes an asset from the network and recomputes nearest
dependencies to measure cascading infrastructure impact.

The simulator reports:
- dependency changes
- distance increases
- impacted assets
### Example Simulation Output

![Outage A001](week01/docs/img/docs:img:outage_A001.png)
![Outage A004](week01/docs/img/docs:img:outage_A004.png)
![IRADashboard](week01/docs/img/I.R.A. Dashboard.png)
![Simulator](week01/docs/img/InfrastructureDigitalTwinSimulator.png)

Infrastructure Resilience Modeling
- Distance outage impact
- Graph network criticality
- Interactive infrastructure map

Infrastructure Digital Twin Simulator

This project includes a live Infrastructure Digital Twin Simulator that models how critical infrastructure networks behave under failure conditions and recommends improvements to increase resilience.

The simulator combines geospatial data, graph network modeling, probabilistic failure simulation, and optimization algorithms to evaluate infrastructure risk and identify the most effective upgrades.

Core Capabilities

The system models infrastructure as a connected network and evaluates how failures impact connectivity.

Features include:
	•	Asset ingestion from geospatial datasets
	•	Graph-based network modeling using NetworkX
	•	Critical node detection via articulation point analysis
	•	Distance-based outage simulation
	•	Monte Carlo resilience simulation to evaluate probabilistic failures
	•	Infrastructure optimization recommending:
	•	redundant network links
	•	optimal locations for new infrastructure nodes
	•	Interactive digital twin visualization using Folium maps

The result is a lightweight digital twin that allows planners to test infrastructure resilience and simulate improvements before deployment.
The simulator runs a multi-stage analysis pipeline:
Infrastructure Data
      ↓
Graph Network Model
      ↓
Failure Simulation
      ↓
Monte Carlo Resilience Analysis
      ↓
Optimization Engine
      ↓
Recommended Infrastructure Improvements
The system evaluates both existing network vulnerabilities and proposed upgrades to determine which improvements provide the greatest resilience benefit.
Infrastructure Optimization

Two optimization methods are included:

Redundant Link Optimization
Tests potential new connections between infrastructure nodes and evaluates how they improve network resilience.

Example output:
Add redundant link A003 ↔ A004
Resilience improvement: +0.0033
New Node Placement Optimization
Generates candidate infrastructure locations and evaluates how a new node would affect network connectivity during failures
Example output:
Recommended build site:
Lat: 40.416260
Lon: -111.790396

Δ components: 0.050
Δ LCC ratio: 0.0154
Resilience score: 0.0654
Interactive Infrastructure Map

The digital twin includes an interactive map displaying:
	•	existing infrastructure assets
	•	nearest network connections
	•	risk radius zones
	•	recommended new infrastructure build sites

Example:
Running the Simulator

Generate node placement recommendations:
python place_new_node.py \
  --k 2 \
  --k-attach 2 \
  --fail-prob 0.15 \
  --trials 500 \
  --grid-n 8 \
  --top 10
  Build the interactive digital twin map:
  python map_assets.py
  Open the generated map:
  map_assets.html
  Technology Stack
	•	Python
	•	GeoPandas
	•	NetworkX
	•	Folium
	•	Pandas
	•	Monte Carlo simulation
Potential Applications

This digital twin architecture can support:
	•	telecom network planning
	•	power grid resilience modeling
	•	transportation infrastructure planning
	•	disaster preparedness simulations
	•	smart city infrastructure analysis
![RecommendedSites](week01/docs/img/Recommended Build Sites.png)
