import os
import boto3
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("AWS_BUCKET")
REGION = os.getenv("AWS_REGION", "us-east-1")
LOCAL_FILE = "assets_clean.csv"
S3_KEY = "week01/assets_clean.csv"


def validate_config() -> None:
    if not BUCKET:
        raise RuntimeError("Missing AWS_BUCKET in environment variables")


def main() -> None:
    validate_config()

    if not os.path.exists(LOCAL_FILE):
        raise FileNotFoundError(
            f"Missing {LOCAL_FILE}. Run clean_assets.py first."
        )

    s3 = boto3.client("s3", region_name=REGION)

    # Upload
    s3.upload_file(LOCAL_FILE, BUCKET, S3_KEY)
    print(f"Uploaded {LOCAL_FILE} -> s3://{BUCKET}/{S3_KEY}")

    # Confirm objects exist
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="week01/")
    keys = [obj["Key"] for obj in resp.get("Contents", [])]

    print("\nBucket objects under week01/:")
    for k in keys:
        print("-", k)


if __name__ == "__main__":
    main()