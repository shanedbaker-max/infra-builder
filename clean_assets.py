import csv
import sys
from typing import Dict, List, Tuple

REQUIRED_COLUMNS = ["asset_id", "asset_type", "city", "lat", "lon", "status"]
INPUT_FILE = "assets_raw.csv"
OUTPUT_FILE = "assets_clean.csv"


def is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_row(row: Dict[str, str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    # Required fields present and non-empty
    for col in REQUIRED_COLUMNS:
        if col not in row:
            errors.append(f"missing_column:{col}")
        elif row[col].strip() == "":
            errors.append(f"blank:{col}")

    # Type checks
    if "lat" in row and row.get("lat", "").strip() != "" and not is_float(row["lat"]):
        errors.append("invalid_float:lat")
    if "lon" in row and row.get("lon", "").strip() != "" and not is_float(row["lon"]):
        errors.append("invalid_float:lon")

    return (len(errors) == 0, errors)


def main() -> None:
    total = 0
    valid = 0
    invalid = 0
    by_type: Dict[str, int] = {}
    error_log: List[Dict[str, str]] = []

    with open(INPUT_FILE, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)

        # Validate header
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

                # Normalize fields
                row["asset_id"] = row["asset_id"].strip().upper()
                row["asset_type"] = row["asset_type"].strip().lower()
                row["city"] = row["city"].strip().title()
                row["status"] = row["status"].strip().upper()

                # Track counts by type
                by_type[row["asset_type"]] = by_type.get(row["asset_type"], 0) + 1

                cleaned_rows.append(row)
            else:
                invalid += 1
                error_log.append(
                    {
                        "asset_id": row.get("asset_id", "").strip(),
                        "errors": "|".join(errors),
                    }
                )

    # Write cleaned output
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    # Print summary
    print("CLEANING SUMMARY")
    print(f"Input file:  {INPUT_FILE}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Total rows:  {total}")
    print(f"Valid rows:  {valid}")
    print(f"Invalid rows:{invalid}")
    print("")
    print("COUNT BY ASSET TYPE")
    for k in sorted(by_type.keys()):
        print(f"- {k}: {by_type[k]}")

    # Print invalid row report
    if error_log:
        print("\nINVALID ROWS")
        for item in error_log:
            print(f"- {item['asset_id'] or '(missing id)'} -> {item['errors']}")

    # Quality gate
    quality = valid / total if total else 0
    min_quality = 0.80

    if quality < min_quality:
        print(f"\nQUALITY GATE: FAIL (quality={quality:.2%}, required={min_quality:.0%})")
        sys.exit(1)

    print(f"\nQUALITY GATE: PASS (quality={quality:.2%}, required={min_quality:.0%})")


if __name__ == "__main__":
    main()