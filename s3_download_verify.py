import os
import boto3

BUCKET = "infra-builder-1727579606"
S3_KEY = "week01/assets_clean.csv"
LOCAL_ORIGINAL = "assets_clean.csv"
LOCAL_DOWNLOADED = "assets_downloaded.csv"


def main() -> None:
    s3 = boto3.client("s3")

    # Download
    s3.download_file(BUCKET, S3_KEY, LOCAL_DOWNLOADED)
    print(f"Downloaded s3://{BUCKET}/{S3_KEY} -> {LOCAL_DOWNLOADED}")

    # Compare file sizes
    original_size = os.path.getsize(LOCAL_ORIGINAL)
    downloaded_size = os.path.getsize(LOCAL_DOWNLOADED)

    print("\nFile size comparison:")
    print("Original size:", original_size)
    print("Downloaded size:", downloaded_size)

    if original_size == downloaded_size:
        print("\nIntegrity check: PASS")
    else:
        print("\nIntegrity check: FAIL")


if __name__ == "__main__":
    main()