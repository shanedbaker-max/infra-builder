import csv
import json
import logging
import sys
from typing import Dict, List, Tuple

REQUIRED_COLUMNS = ["asset_id", "asset_type", "city", "lat", "lon", "status"]
INPUT_FILE = "assets_raw.csv"
OUTPUT_FILE = "assets_clean.csv"
INVALID_FILE = "invalid_assets.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_row(row: Dict[str, str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    for col in REQUIRED_COLUMNS:
        if col not in row:
            errors.append(f"missing_column:{col}")
        elif row[col].strip() == "":
            errors.append(f"blank:{col}")

    if "lat" in row and row.get("lat", "").strip() != "" and not is_float(row["lat"]):
        errors.append("invalid_float:lat")
    if "lon" in row and row.get("lon", "").strip() != "" and not is_float(row["lon"]):
        errors.append("invalid_float:lon")

    return (len(errors) == 0, errors)


def attempt_repair(row: dict, reasons: list) -> tuple:
    """
    Returns:
      (repaired_ok, repaired_row, repair_tag)
    Only repairs:
      - blank:city   -> city="UNKNOWN"
      - blank:status -> status="UNKNOWN"
    If any other reason exists, no repair.
    """
    allowed = {"blank:city", "blank:status"}
    if any(r not in allowed for r in reasons):
        return False, row, ""

    repaired = dict(row)
    tag_parts = []

    if "blank:city" in reasons:
        repaired["city"] = "UNKNOWN"
        tag_parts.append("city_unknown")
    if "blank:status" in reasons:
        repaired["status"] = "UNKNOWN"
        tag_parts.append("status_unknown")

    return True, repaired, "+".join(tag_parts)


def main() -> None:
    invalid_records: List[Dict[str, str]] = []
    repaired_records: List[Dict[str, str]] = []
    total = 0
    valid = 0
    invalid = 0
    by_type: Dict[str, int] = {}
    error_log: List[Dict[str, str]] = []

    with open(INPUT_FILE, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)

        header = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise ValueError(f"Input file missing required columns: {missing}")

        cleaned_rows: List[Dict[str, str]] = []

        for row in reader:
            total += 1
            ok, errors = validate_row(row)

            if ok:
                valid += 1
                row["asset_id"] = row["asset_id"].strip().upper()
                row["asset_type"] = row["asset_type"].strip().lower()
                row["city"] = row["city"].strip().title()
                row["status"] = row["status"].strip().upper()
                by_type[row["asset_type"]] = by_type.get(row["asset_type"], 0) + 1
                cleaned_rows.append(row)

            else:
                repaired_ok, repaired_row, repair_tag = attempt_repair(row, errors)

                if repaired_ok:
                    # Re-validate the repaired row
                    reasons2 = []
                    if not repaired_row.get("city", "").strip():
                        reasons2.append("blank:city")
                    if not repaired_row.get("status", "").strip():
                        reasons2.append("blank:status")
                    for field in ("lat", "lon"):
                        try:
                            float(repaired_row.get(field, ""))
                        except (TypeError, ValueError):
                            reasons2.append(f"invalid_float:{field}")

                    if not reasons2:
                        # Repair succeeded — normalize and accept
                        repaired_row["asset_id"] = repaired_row["asset_id"].strip().upper()
                        repaired_row["asset_type"] = repaired_row["asset_type"].strip().lower()
                        repaired_row["city"] = repaired_row["city"].strip().title()
                        repaired_row["status"] = repaired_row["status"].strip().upper()
                        repaired_records.append({
                            "asset_id": repaired_row.get("asset_id", ""),
                            "repair": repair_tag,
                        })
                        by_type[repaired_row["asset_type"]] = by_type.get(repaired_row["asset_type"], 0) + 1
                        cleaned_rows.append(repaired_row)
                        valid += 1
                    else:
                        # Repair did not fully resolve errors
                        invalid += 1
                        invalid_records.append(row)
                        error_log.append({
                            "asset_id": row.get("asset_id", "").strip(),
                            "errors": "|".join(reasons2),
                        })
                else:
                    # Unrepairable
                    invalid += 1
                    invalid_records.append(row)
                    error_log.append({
                        "asset_id": row.get("asset_id", "").strip(),
                        "errors": "|".join(errors),
                    })

    # Write cleaned output (valid + repaired)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    # Write quarantine file
    if invalid_records:
        with open(INVALID_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=invalid_records[0].keys())
            writer.writeheader()
            writer.writerows(invalid_records)
        print(f"\nQuarantine file written: {INVALID_FILE} ({len(invalid_records)} rows)")

    # Print summary
    logger.info("Cleaning summary starting")
    print(f"Input file:  {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Total rows:  {total}")
    print(f"Valid rows:  {valid}")
    print(f"Repaired rows: {len(repaired_records)}")
    print(f"Invalid rows:{invalid}")
    print("")
    print("COUNT BY ASSET TYPE")
    for k in sorted(by_type.keys()):
        print(f"- {k}: {by_type[k]}")

    if repaired_records:
        print("\nREPAIRED ROWS")
        for item in repaired_records:
            print(f"- {item['asset_id']} -> {item['repair']}")

    if error_log:
        print("\nINVALID ROWS")
        for item in error_log:
            print(f"- {item['asset_id'] or '(missing id)'} -> {item['errors']}")

    # Write metrics
    metrics = {
        "total_rows": total,
        "valid_rows": valid,
        "invalid_rows": invalid,
        "repaired_rows": len(repaired_records),
        "quality_score": valid / total if total else 0,
    }

    with open("pipeline_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("\nMetrics written to pipeline_metrics.json")
    logger.info(f"rows_processed total={total} valid={valid} invalid={invalid}")
    logger.info(f"rows_repaired count={len(repaired_records)}")

    # Quality gate
    quality = valid / total if total else 0
    min_quality = 0.80

    if quality < min_quality:
        print(f"\nQUALITY GATE: FAIL (quality={quality:.2%}, required={min_quality:.0%})")
        sys.exit(1)

    print(f"\nQUALITY GATE: PASS (quality={quality:.2%}, required={min_quality:.0%})")


if __name__ == "__main__":
    main()