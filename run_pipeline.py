import subprocess
import sys


def run_step(name: str, command: list[str]) -> None:
    print(f"\n--- Running: {name} ---")

    result = subprocess.run(command)

    if result.returncode != 0:
        print(f"\n❌ Step failed: {name}")
        sys.exit(1)

    print(f"✅ Completed: {name}")


def main() -> None:
    run_step("Clean assets", ["python", "clean_assets.py"])
    run_step("Upload to S3", ["python", "s3_upload.py"])
    run_step("Download + verify", ["python", "s3_download_verify.py"])

    print("\n🎉 Pipeline finished successfully")


if __name__ == "__main__":
    main()