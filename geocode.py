"""Geocoding utility using Nominatim (free, no API key)."""

import time
import urllib.request
import urllib.parse
import json

_last_request = 0


def geocode_address(address, city, state='NH', zip_code=''):
    """Convert address to (latitude, longitude) using Nominatim.

    Returns (lat, lng) or (None, None) on failure.
    Rate-limited to 1 request per second per Nominatim policy.
    """
    global _last_request

    parts = [p for p in [address, city, state, zip_code] if p]
    query = ', '.join(parts)
    if not query:
        return None, None

    # Respect rate limit
    elapsed = time.time() - _last_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    params = urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'us',
    })
    url = f'https://nominatim.openstreetmap.org/search?{params}'

    req = urllib.request.Request(url, headers={
        'User-Agent': 'NHCPRChallenge/1.0 (info@cprchallengenh.com)',
    })

    try:
        _last_request = time.time()
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass

    return None, None
