import subprocess
import sys
import logging
import json
import os


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


def run_step(name: str, command: list[str]) -> None:
    logger.info(f"pipeline_step_start step={name}")

    result = subprocess.run(command)

    if result.returncode != 0:
        logger.error(f"pipeline_step_failed step={name}")
        sys.exit(1)

    logger.info(f"pipeline_step_complete step={name}")


def print_pipeline_report() -> None:
    metrics_file = "pipeline_metrics.json"

    if not os.path.exists(metrics_file):
        logger.warning("pipeline_metrics_missing")
        return

    with open(metrics_file) as f:
        metrics = json.load(f)

    logger.info(
        f"pipeline_metrics total={metrics['total_rows']} "
        f"valid={metrics['valid_rows']} "
        f"invalid={metrics['invalid_rows']} "
        f"quality={metrics['quality_score']:.2%}"
    )


def main() -> None:
    run_step("Clean assets", ["python", "clean_assets.py"])

    print_pipeline_report()

    run_step("Upload to S3", ["python", "s3_upload.py"])
    run_step("Download + verify", ["python", "s3_download_verify.py"])

    logger.info("pipeline_complete status=success")


if __name__ == "__main__":
    main()