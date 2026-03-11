import csv
import os
from geocoding_lib import load_api_key, batch_geocode

def load_existing_results(filepath: str, num_rows: int):
    """Load existing output.csv and return list of result dicts (or None per row)."""
    if not os.path.exists(filepath):
        return None

    existing = [None] * num_rows
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= num_rows:
                break
            lat = row.get("latitude", "")
            lon = row.get("longitude", "")
            if lat and lon:
                try:
                    existing[i] = {
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "confidence": float(row["confidence"]) if row.get("confidence") else None,
                        "label": row.get("label", ""),
                        "source": row.get("source", ""),
                        "raw_response": None,
                        "error": row.get("geocoding_error") or None
                    }
                except (ValueError, KeyError):
                    pass
    return existing

def main():
    api_key = load_api_key("api_key.txt")

    with open("input.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows...\n")

    queries = []
    for row in rows:
        loc_desc = row["Location Description"].strip()
        query = loc_desc if loc_desc else row["Geocoding Query"]
        queries.append(query)

    # Load existing results to skip valid ones
    existing = load_existing_results("output.csv", len(rows))

    results = batch_geocode(queries, api_key, existing_results=existing)

    # Prepare output
    output_rows = []
    for row, result in zip(rows, results):
        output_row = dict(row)
        output_row["latitude"] = result["latitude"]
        output_row["longitude"] = result["longitude"]
        output_row["confidence"] = result["confidence"]
        output_row["label"] = result["label"]
        output_row["source"] = result["source"]
        output_row["geocoding_error"] = result["error"]
        output_rows.append(output_row)

    # Write output CSV
    if output_rows:
        fieldnames = list(output_rows[0].keys())
        with open("output.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)

        print(f"\nSuccessfully wrote {len(output_rows)} rows to output.csv")

if __name__ == "__main__":
    main()
