import csv
import sys
from geocoding_lib import load_api_key, batch_geocode

def main():
    # Load API key
    api_key = load_api_key("api_key.txt")

    # Read input CSV
    with open("input.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows...\n")

    # Extract queries - try Location Description first, then Geocoding Query as fallback
    queries = []
    for row in rows:
        loc_desc = row["Location Description"].strip()
        query = loc_desc if loc_desc else row["Geocoding Query"]
        queries.append(query)

    results = batch_geocode(queries, api_key)

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
        print("\nResults preview:")
        for row in output_rows:
            print(f"  {row['Name']}: ({row['latitude']}, {row['longitude']}) - Confidence: {row['confidence']}")
    else:
        print("No results to write")

if __name__ == "__main__":
    main()
