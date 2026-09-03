"""
Safar-e-Taleem — Geo Services (free & keyless)

  • geocode(query)        — address → coordinates via OpenStreetMap Nominatim
                            (restricted to Pakistan, 24h server-side cache)
  • walking_route(...)    — real walking route via the public OSRM demo server,
                            with a straight-line interpolation fallback so the
                            live-tracking demo keeps working offline.

Both functions never raise: any failure degrades to an empty/interpolated
result, keeping the dashboard and registration flow responsive.
"""
import logging
import time

import requests

from modules.commute_engine import distance_km

logger = logging.getLogger('safar-e-taleem.geo')

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OSRM_URL = 'https://router.project-osrm.org/route/v1/foot/{start};{end}'
# Nominatim usage policy requires a meaningful, contactable User-Agent.
USER_AGENT = 'Safar-e-Taleem/1.0 (school transport app; demo)'

GEOCODE_TTL = 24 * 3600  # 24 hours

# query -> (timestamp, results)
_geocode_cache = {}


# ---------------------------------------------------------
# GEOCODING (Nominatim)
# ---------------------------------------------------------

def geocode(query, limit=5):
    """
    Convert a free-text address to coordinates using Nominatim
    (Pakistan results only). Returns a list of dicts:
        [{'label': display_name, 'latitude': float, 'longitude': float}, ...]
    Returns [] when the query is too short or the service fails.
    """
    q = (query or '').strip()
    if len(q) < 3:
        return []

    now = time.time()
    cached = _geocode_cache.get(q)
    if cached and (now - cached[0]) < GEOCODE_TTL:
        return cached[1]

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={'q': q, 'format': 'jsonv2', 'countrycodes': 'pk', 'limit': limit},
            headers={'User-Agent': USER_AGENT},
            timeout=8,
        )
        if resp.status_code == 200:
            results = [
                {
                    'label': item.get('display_name', ''),
                    'latitude': float(item['lat']),
                    'longitude': float(item['lon']),
                }
                for item in resp.json()
                if item.get('lat') and item.get('lon')
            ]
            _geocode_cache[q] = (now, results)
            return results
        logger.warning('Nominatim returned HTTP %s for %r', resp.status_code, q)
    except Exception as e:
        logger.warning('Geocode failed for %r: %s', q, e)

    return []


# ---------------------------------------------------------
# WALKING ROUTE (OSRM demo server)
# ---------------------------------------------------------

def _interpolate(start_lat, start_lon, end_lat, end_lon, points=10):
    """Evenly spaced straight-line waypoints between two coordinates."""
    return [
        [
            round(start_lat + (end_lat - start_lat) * i / (points - 1), 6),
            round(start_lon + (end_lon - start_lon) * i / (points - 1), 6),
        ]
        for i in range(points)
    ]


def walking_route(start_lat, start_lon, end_lat, end_lon):
    """
    Real walking route (OSRM foot profile) between two points.
    Returns {'distance_km', 'duration_min', 'waypoints': [[lat, lon], ...], 'source'}.
    Falls back to a straight-line interpolation when OSRM is unreachable,
    estimating duration at an average walking pace of 4.5 km/h.
    """
    start = f'{start_lon},{start_lat}'
    end = f'{end_lon},{end_lat}'
    try:
        resp = requests.get(
            OSRM_URL.format(start=start, end=end),
            params={'overview': 'full', 'geometries': 'geojson'},
            headers={'User-Agent': USER_AGENT},
            timeout=8,
        )
        data = resp.json()
        route = data['routes'][0]
        # OSRM geometry is [lon, lat] — flip to Leaflet's [lat, lon]
        waypoints = [[lat, lon] for lon, lat in route['geometry']['coordinates']]
        if len(waypoints) >= 2:
            return {
                'distance_km': round(route['distance'] / 1000, 2),
                'duration_min': round(route['duration'] / 60),
                'waypoints': waypoints,
                'source': 'osrm',
            }
    except Exception as e:
        logger.warning('OSRM route failed (%s) — interpolating straight line', e)

    waypoints = _interpolate(start_lat, start_lon, end_lat, end_lon)
    dist = distance_km(start_lat, start_lon, end_lat, end_lon)
    return {
        'distance_km': round(dist, 2),
        'duration_min': round(dist / 4.5 * 60),
        'waypoints': waypoints,
        'source': 'interpolated',
    }
