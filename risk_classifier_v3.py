import csv
from typing import Dict, List

INPUT_FILE = "assets_raw.csv"


def classify_risk(status: str) -> str:
    status = status.strip().upper()

    if status == "MAINT":
        return "HIGH"
    elif status == "ACTIVE":
        return "LOW"
    elif status == "":
        return "HIGH"
    else:
        return "UNKNOWN"


def main():
    summary: Dict[str, Dict[str, object]] = {}
    total = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total += 1

            asset_id = row["asset_id"].strip().upper()
            status = row["status"]

            risk = classify_risk(status)

            if risk not in summary:
                summary[risk] = {"count": 0, "assets": []}

            summary[risk]["count"] += 1
            summary[risk]["assets"].append(asset_id)

    print(f"RISK SUMMARY — Dynamic")
    print(f"Total: {total}\n")
    for level, data in summary.items():
        print(f"{level}: {data['count']} assets")
        if data["assets"]:
            print(f"  Assets: {', '.join(data['assets'])}")


if __name__ == "__main__":
    main()
