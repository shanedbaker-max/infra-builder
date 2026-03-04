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