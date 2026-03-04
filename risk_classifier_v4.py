import csv
from typing import Dict, Set

INPUT_FILE = "assets_raw.csv"
ALLOWED_RISKS: Set[str] = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}


def classify_risk(status: str) -> str:
    status = status.strip().upper()

    if status == "MAINT":
        return "HIGH"
    elif status == "ACTIVE":
        return "LOW"
    elif status == "":
        return "HIGH"
    else:
        # Intentionally return something NOT in allowlist sometimes
        return "UNEXPECTED_STATUS"


def main():
    summary: Dict[str, Dict[str, object]] = {}
    total = 0
    unexpected_values: Dict[str, int] = {}

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total += 1

            asset_id = row["asset_id"].strip().upper()
            raw_status = row["status"]

            risk = classify_risk(raw_status)

            # Enforce allowlist
            if risk not in ALLOWED_RISKS:
                normalized = raw_status.strip().upper()
                log_key = "(BLANK)" if normalized == "" else normalized
                unexpected_values[log_key] = unexpected_values.get(log_key, 0) + 1
                risk = "UNKNOWN"

            # Dynamic aggregation — only allowed keys ever enter summary
            summary.setdefault(risk, {"count": 0, "assets": []})
            summary[risk]["count"] += 1
            summary[risk]["assets"].append(asset_id)

    print("RISK SUMMARY — Allowlist + Dynamic")
    print("Total:", total)
    for category in sorted(summary.keys()):
        data = summary[category]
        print(f"\n{category}: {data['count']} assets")
        print("Assets:", ", ".join(data["assets"]))

    if unexpected_values:
        print("\nUNEXPECTED RAW STATUS VALUES")
        for k in sorted(unexpected_values.keys()):
            print(f"- {k!r}: {unexpected_values[k]}")


if __name__ == "__main__":
    main()