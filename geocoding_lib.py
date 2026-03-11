import requests
import json
import time
from typing import Dict, List, Optional


def load_api_key(filepath: str) -> str:
    """Load Geocode.Earth API key from file."""
    with open(filepath, 'r') as f:
        return f.read().strip()


def _geocode_nominatim(query: str) -> Dict:
    """Try Nominatim first (free, no API key needed)."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "polygon_geojson": 1,
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
    """Fallback to Geocode.Earth API."""
    url = "https://api.geocode.earth/v1/search"
    params = {
        "text": query,
        "api_key": api_key,
        "size": 1
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

    Returns:
        Dict with keys: latitude, longitude, confidence, label, source, raw_response, error
    """
    cleaned_query = " ".join(query.split())
    empty = {
        "latitude": None, "longitude": None, "confidence": None,
        "label": "", "source": None, "raw_response": None, "error": None
    }

    # Try Nominatim first
    try:
        result = _geocode_nominatim(cleaned_query)
        if result:
            return result
    except Exception as e:
        print(f"  Nominatim error: {e}")

    # Fall back to Geocode.Earth
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


def batch_geocode(queries: List[str], api_key: str) -> List[Dict]:
    """
    Geocode multiple queries. Tries Nominatim first for all queries,
    then rate-limits Geocode.Earth fallbacks to 10 requests/sec.
    """
    empty = lambda: {
        "latitude": None, "longitude": None, "confidence": None,
        "label": "", "source": None, "raw_response": None, "error": None
    }

    results: List[Optional[Dict]] = [None] * len(queries)
    ge_pending: List[int] = []  # indices that need Geocode.Earth fallback

    # Pass 1: try Nominatim for all queries (rate limited to 1 req/sec)
    last_nominatim = 0.0
    for i, query in enumerate(queries):
        cleaned = " ".join(query.split())
        print(f"[nominatim] {i+1}/{len(queries)}: {query}")

        # Nominatim requires max 1 req/sec
        elapsed = time.monotonic() - last_nominatim
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            last_nominatim = time.monotonic()
            result = _geocode_nominatim(cleaned)
            if result:
                results[i] = result
                print(f"  ✓ Found: ({result['latitude']}, {result['longitude']})")
                continue
        except Exception as e:
            print(f"  Nominatim error: {e}")
        ge_pending.append(i)

    # Pass 2: rate-limited Geocode.Earth fallback
    if ge_pending and api_key:
        print(f"\n{len(ge_pending)} queries need Geocode.Earth fallback (rate limited to 10/sec)")
        ge_times: List[float] = []

        for j, idx in enumerate(ge_pending):
            # Enforce 10 req/sec: if we have 10+ requests in the last second, wait
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

    found = sum(1 for r in results if r.get("latitude"))
    print(f"\nDone: {found}/{len(queries)} geocoded successfully")
    return results
