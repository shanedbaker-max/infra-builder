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
