import os
import hashlib

import boto3
from dotenv import load_dotenv


load_dotenv()

BUCKET = os.getenv("AWS_BUCKET")
REGION = os.getenv("AWS_REGION", "us-east-1")

LAST_RUN_FILE = "last_run_id.txt"


def validate_config() -> None:
    if not BUCKET:
        raise RuntimeError("Missing AWS_BUCKET in environment variables (.env)")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def s3_key_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def read_last_run_id() -> str:
    if not os.path.exists(LAST_RUN_FILE):
        raise FileNotFoundError(
            f"Missing {LAST_RUN_FILE}. Run s3_upload.py first so a run_id is recorded."
        )
    with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
        run_id = f.read().strip()
    if not run_id:
        raise RuntimeError(f"{LAST_RUN_FILE} is empty.")
    return run_id


def download_and_verify(s3, name: str, s3_key: str, local_original: str, local_download: str, required: bool) -> None:
    if not os.path.exists(local_original):
        raise FileNotFoundError(f"Missing local file {local_original}. Run clean_assets.py first.")

    if not s3_key_exists(s3, BUCKET, s3_key):
        if required:
            raise RuntimeError(f"Missing required S3 object: s3://{BUCKET}/{s3_key}")
        print(f"\nSkipped optional artifact (not in S3): {s3_key}")
        return

    s3.download_file(BUCKET, s3_key, local_download)
    print(f"\nDownloaded [{name}] s3://{BUCKET}/{s3_key} -> {local_download}")

    orig_size = os.path.getsize(local_original)
    down_size = os.path.getsize(local_download)
    print(f"File size: original={orig_size} downloaded={down_size}")
    if orig_size != down_size:
        raise RuntimeError(f"Size mismatch for {name}")

    orig_hash = sha256_file(local_original)
    down_hash = sha256_file(local_download)
    if orig_hash != down_hash:
        raise RuntimeError(f"Hash mismatch for {name}")

    print("Integrity check: PASS")


def main() -> None:
    validate_config()
    s3 = boto3.client("s3", region_name=REGION)

    run_id = read_last_run_id()
    run_prefix = f"week01/runs/{run_id}/"

    print(f"Verifying run_id: {run_id}")

    artifacts = [
        {
            "name": "clean",
            "s3_key": f"{run_prefix}assets_clean.csv",
            "local_original": "assets_clean.csv",
            "local_download": "assets_clean.downloaded.csv",
            "required": True,
        },
        {
            "name": "metrics",
            "s3_key": f"{run_prefix}metrics/pipeline_metrics.json",
            "local_original": "pipeline_metrics.json",
            "local_download": "pipeline_metrics.downloaded.json",
            "required": True,
        },
        {
            "name": "quarantine",
            "s3_key": f"{run_prefix}quarantine/invalid_assets.csv",
            "local_original": "invalid_assets.csv",
            "local_download": "invalid_assets.downloaded.csv",
            "required": False,
        },
    ]

    for a in artifacts:
        download_and_verify(
            s3,
            a["name"],
            a["s3_key"],
            a["local_original"],
            a["local_download"],
            a["required"],
        )

    print("\n✅ All artifact verifications complete")


if __name__ == "__main__":
    main()