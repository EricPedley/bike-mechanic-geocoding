# Geocoding Pipeline

## How it works

`geocode_test.py` reads `input.csv`, geocodes each row using the "Location Description" column (falling back to "Geocoding Query"), and writes results to `output.csv` with latitude, longitude, confidence, and source columns appended.

Geocoding uses two APIs in sequence:

1. **Nominatim** (OpenStreetMap) — free, no API key, but rate-limited to 1 request/sec. Both APIs are filtered to Kenya-only results (`countrycodes=ke` / `boundary.country=KE`).
2. **Geocode.Earth** — paid fallback for Nominatim misses, rate-limited to 10 requests/sec. API key lives in `api_key.txt` (not uploaded here, only locally on my pc).

Re-running the script is safe — it reads the existing `output.csv` and skips rows that already have valid coordinates inside Kenya. Only missing or obviously wrong results get re-queried.

## Running

```
python geocode_test.py
```

Takes ~4 minutes for a full 363-row run (dominated by Nominatim's 1 req/sec limit). Re-runs are faster since valid results are cached.

## Files

- `geocoding_lib.py` — API wrappers, rate limiting, Kenya bounding box validation
- `geocode_test.py` — main script: reads input, calls geocoder, writes output
- `input.csv` — source data (read-only)
- `output.csv` — results
- `api_key.txt` — Geocode.Earth API key
