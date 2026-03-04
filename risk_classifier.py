import csv

INPUT_FILE = "assets_raw.csv"

def classify_risk(status: str) -> str:
    if status == "MAINT":
        return "HIGH"
    elif status == "ACTIVE":
        return "LOW"
    elif status == "":
        return "HIGH"
    else:
        return "UNKNOWN"

def main():
    total = 0
    high = 0
    medium = 0
    low = 0
    unknown = 0
    unknown_assets = []

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total += 1

            status = row["status"].strip().upper()
            asset_id = row["asset_id"].strip()

            risk = classify_risk(status)

            if risk == "HIGH":
                high += 1
            elif risk == "MEDIUM":
                medium += 1
            elif risk == "LOW":
                low += 1
            elif risk == "UNKNOWN":
                unknown += 1
                unknown_assets.append(asset_id)

    print("RISK SUMMARY")
    print("Total:", total)
    print("High:", high)
    print("Medium:", medium)
    print("Low:", low)
    print("Unknown:", unknown)
    if unknown_assets:
        print("Unknown Assets:", unknown_assets)

if __name__ == "__main__":
    main()