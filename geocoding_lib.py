import requests
import json
import time
from typing import Dict, List, Optional

# Kenya bounding box (approx): lat -4.7 to 5.0, lon 33.9 to 41.9
KENYA_LAT_MIN = -5.0
KENYA_LAT_MAX = 5.5
KENYA_LON_MIN = 33.5
KENYA_LON_MAX = 42.0


def load_api_key(filepath: str) -> str:
    """Load Geocode.Earth API key from file."""
    with open(filepath, 'r') as f:
        return f.read().strip()


def is_in_kenya(lat: float, lon: float) -> bool:
    """Check if coordinates fall within Kenya's bounding box."""
    if lat is None or lon is None:
        return False
    return KENYA_LAT_MIN <= lat <= KENYA_LAT_MAX and KENYA_LON_MIN <= lon <= KENYA_LON_MAX


def _geocode_nominatim(query: str) -> Dict:
    """Try Nominatim with country code filter for Kenya."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "countrycodes": "ke",
        "format": "jsonv2"
    }

    response = requests.get(url, params=params, headers={"User-Agent": "GecodingApp/1.0"})
    response.raise_for_status()
    data = response.json()

    if isinstance(data, list) and len(data) > 0:
        result = data[0]
        return {
            "latitude": float(result.get("lat")) if result.get("lat") else None,
            "longitude": float(result.get("lon")) if result.get("lon") else None,
            "confidence": float(result.get("importance", 0)) if result.get("importance") else None,
            "label": result.get("display_name", ""),
            "source": "nominatim",
            "raw_response": data,
            "error": None
        }
    return None


def _geocode_earth(query: str, api_key: str) -> Dict:
    """Fallback to Geocode.Earth API, filtered to Kenya."""
    url = "https://api.geocode.earth/v1/search"
    params = {
        "text": query,
        "api_key": api_key,
        "size": 1,
        "boundary.country": "KE"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data.get("features") and len(data["features"]) > 0:
        feature = data["features"][0]
        coords = feature.get("geometry", {}).get("coordinates", [])
        props = feature.get("properties", {})
        return {
            "latitude": coords[1] if len(coords) > 1 else None,
            "longitude": coords[0] if len(coords) > 0 else None,
            "confidence": props.get("confidence", None),
            "label": props.get("label", ""),
            "source": "geocode.earth",
            "raw_response": data,
            "error": None
        }
    return None


def geocode(query: str, api_key: str = None) -> Dict:
    """
    Geocode a query. Tries Nominatim first, falls back to Geocode.Earth.
    Both are filtered to Kenya.
    """
    cleaned_query = " ".join(query.split())
    empty = {
        "latitude": None, "longitude": None, "confidence": None,
        "label": "", "source": None, "raw_response": None, "error": None
    }

    try:
        result = _geocode_nominatim(cleaned_query)
        if result:
            return result
    except Exception as e:
        print(f"  Nominatim error: {e}")

    if api_key:
        try:
            result = _geocode_earth(cleaned_query, api_key)
            if result:
                return result
        except Exception as e:
            empty["error"] = f"Geocode.Earth error: {str(e)}"
            return empty

    empty["error"] = "No results found"
    return empty


def batch_geocode(queries: List[str], api_key: str, existing_results: List[Optional[Dict]] = None) -> List[Dict]:
    """
    Geocode multiple queries. Tries Nominatim first for all queries,
    then rate-limits Geocode.Earth fallbacks to 10 requests/sec.

    If existing_results is provided, skips queries that already have valid
    results within Kenya.
    """
    empty = lambda: {
        "latitude": None, "longitude": None, "confidence": None,
        "label": "", "source": None, "raw_response": None, "error": None
    }

    results: List[Optional[Dict]] = [None] * len(queries)
    needs_geocoding: List[int] = []

    # Determine which queries need (re-)geocoding
    for i in range(len(queries)):
        if existing_results and i < len(existing_results) and existing_results[i]:
            ex = existing_results[i]
            lat, lon = ex.get("latitude"), ex.get("longitude")
            if lat is not None and lon is not None and is_in_kenya(lat, lon):
                results[i] = ex
                continue
        needs_geocoding.append(i)

    if not needs_geocoding:
        print("All queries already have valid results. Nothing to do.")
        return results

    skipped = len(queries) - len(needs_geocoding)
    if skipped > 0:
        print(f"Skipping {skipped} queries with valid existing results")
    print(f"{len(needs_geocoding)} queries to geocode\n")

    ge_pending: List[int] = []

    # Pass 1: try Nominatim for pending queries (rate limited to 1 req/sec)
    last_nominatim = 0.0
    for j, idx in enumerate(needs_geocoding):
        cleaned = " ".join(queries[idx].split())
        print(f"[nominatim] {j+1}/{len(needs_geocoding)}: {queries[idx]}")

        elapsed = time.monotonic() - last_nominatim
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            last_nominatim = time.monotonic()
            result = _geocode_nominatim(cleaned)
            if result:
                results[idx] = result
                print(f"  ✓ Found: ({result['latitude']}, {result['longitude']})")
                continue
        except Exception as e:
            print(f"  Nominatim error: {e}")
        ge_pending.append(idx)

    # Pass 2: rate-limited Geocode.Earth fallback
    if ge_pending and api_key:
        print(f"\n{len(ge_pending)} queries need Geocode.Earth fallback (rate limited to 10/sec)")
        ge_times: List[float] = []

        for j, idx in enumerate(ge_pending):
            now = time.monotonic()
            ge_times = [t for t in ge_times if now - t < 1.0]
            if len(ge_times) >= 10:
                wait = 1.0 - (now - ge_times[0])
                if wait > 0:
                    time.sleep(wait)
                ge_times = [t for t in ge_times if time.monotonic() - t < 1.0]

            cleaned = " ".join(queries[idx].split())
            print(f"[geocode.earth] {j+1}/{len(ge_pending)}: {queries[idx]}")
            try:
                result = _geocode_earth(cleaned, api_key)
                if result:
                    results[idx] = result
                    print(f"  ✓ Found: ({result['latitude']}, {result['longitude']})")
                    ge_times.append(time.monotonic())
                    continue
            except Exception as e:
                print(f"  Geocode.Earth error: {e}")

            ge_times.append(time.monotonic())
            r = empty()
            r["error"] = "No results found"
            results[idx] = r

    # Fill any remaining None results
    for i in range(len(results)):
        if results[i] is None:
            r = empty()
            r["error"] = "No results found"
            results[i] = r

    found = sum(1 for r in results if r.get("latitude") and is_in_kenya(r["latitude"], r["longitude"]))
    print(f"\nDone: {found}/{len(queries)} geocoded successfully (in Kenya)")
    return results
