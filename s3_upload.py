import os
from datetime import datetime, timezone

import boto3
from dotenv import load_dotenv


load_dotenv()

BUCKET = os.getenv("AWS_BUCKET")
REGION = os.getenv("AWS_REGION", "us-east-1")

CLEAN_FILE = "assets_clean.csv"
QUARANTINE_FILE = "invalid_assets.csv"
METRICS_FILE = "pipeline_metrics.json"

LAST_RUN_FILE = "last_run_id.txt"

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_PREFIX = f"week01/runs/{RUN_ID}/"

S3_RUN_CLEAN_KEY = f"{RUN_PREFIX}assets_clean.csv"
S3_RUN_METRICS_KEY = f"{RUN_PREFIX}metrics/pipeline_metrics.json"
S3_RUN_QUARANTINE_KEY = f"{RUN_PREFIX}quarantine/invalid_assets.csv"

S3_LATEST_CLEAN_KEY = "week01/latest/assets_clean.csv"
S3_LATEST_METRICS_KEY = "week01/latest/metrics/pipeline_metrics.json"
S3_LATEST_QUARANTINE_KEY = "week01/latest/quarantine/invalid_assets.csv"


def validate_config() -> None:
    if not BUCKET:
        raise RuntimeError("Missing AWS_BUCKET in environment variables (.env)")


def file_exists_nonempty(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 0


def upload_file(s3, local_path: str, bucket: str, key: str) -> None:
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Missing {local_path}. Run clean_assets.py first.")
    s3.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} -> s3://{bucket}/{key}")


def list_prefix(s3, bucket: str, prefix: str) -> None:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    keys = [obj["Key"] for obj in resp.get("Contents", [])]
    print(f"\nBucket objects under {prefix}:")
    if not keys:
        print("(none)")
        return
    for k in keys:
        print("-", k)


def write_last_run_id(run_id: str) -> None:
    # Always write to current working directory (week01)
    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        f.write(run_id + "\n")


def main() -> None:
    validate_config()
    s3 = boto3.client("s3", region_name=REGION)

    print(f"Run ID: {RUN_ID}")
    print(f"Upload prefix: s3://{BUCKET}/{RUN_PREFIX}\n")

    # Upload immutable run artifacts
    upload_file(s3, CLEAN_FILE, BUCKET, S3_RUN_CLEAN_KEY)
    upload_file(s3, METRICS_FILE, BUCKET, S3_RUN_METRICS_KEY)

    # Upload latest pointers (copies)
    upload_file(s3, CLEAN_FILE, BUCKET, S3_LATEST_CLEAN_KEY)
    upload_file(s3, METRICS_FILE, BUCKET, S3_LATEST_METRICS_KEY)

    # Quarantine optional
    if file_exists_nonempty(QUARANTINE_FILE):
        upload_file(s3, QUARANTINE_FILE, BUCKET, S3_RUN_QUARANTINE_KEY)
        upload_file(s3, QUARANTINE_FILE, BUCKET, S3_LATEST_QUARANTINE_KEY)
    else:
        print(f"Skipped quarantine upload (missing or empty): {QUARANTINE_FILE}")

    # Record run id for verifier
    write_last_run_id(RUN_ID)
    print(f"\nWrote {LAST_RUN_FILE}: {RUN_ID}")

    # Confirm
    list_prefix(s3, BUCKET, RUN_PREFIX)
    list_prefix(s3, BUCKET, "week01/latest/")


if __name__ == "__main__":
    main()