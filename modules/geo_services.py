"""
Safar-e-Taleem — Geo Services (free & keyless)

  • geocode(query)        — address → coordinates via OpenStreetMap Nominatim
                            (restricted to Pakistan, 24h server-side cache)
  • walking_route(...)    — road-following route geometry from the public OSRM
                            demo server, timed at a walking pace, with a
                            straight-line interpolation fallback so the
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

# Average pace for a child walking to school. We have to derive the walking TIME
# ourselves: the public OSRM demo server ignores the profile segment completely
# -- 'foot', 'driving', 'bike' and even nonsense profiles all return the
# byte-identical CAR route (measured on the same coordinate pair: 1.53 km in
# 3.1 min = 29 km/h for every profile tried). Its geometry is still worth
# having because it follows the real road network, but its duration is a driving
# time, and trusting it would tell a parent a 1.5 km walk takes 3 minutes.
WALKING_SPEED_KMH = 4.5

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


def _walking_minutes(km):
    """Distance -> minutes at WALKING_SPEED_KMH, never below a minute."""
    return max(1, round(km / WALKING_SPEED_KMH * 60))


def walking_route(start_lat, start_lon, end_lat, end_lon):
    """
    Road-following route between two points, timed at a walking pace.

    Returns {'distance_km', 'duration_min', 'waypoints': [[lat, lon], ...],
    'source'}, where source is 'osrm' when the geometry came from the road
    network and 'interpolated' when it is a straight-line stand-in (OSRM
    unreachable), so an offline demo still draws something.

    `duration_min` is ALWAYS derived from `distance_km` at WALKING_SPEED_KMH and
    never taken from OSRM -- see the note on that constant.
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
            km = round(route['distance'] / 1000, 2)
            return {
                'distance_km': km,
                # Deliberately NOT route['duration']: that is a driving time.
                'duration_min': _walking_minutes(km),
                'waypoints': waypoints,
                'source': 'osrm',
            }
    except Exception as e:
        logger.warning('OSRM route failed (%s) — interpolating straight line', e)

    waypoints = _interpolate(start_lat, start_lon, end_lat, end_lon)
    dist = round(distance_km(start_lat, start_lon, end_lat, end_lon), 2)
    return {
        'distance_km': dist,
        'duration_min': _walking_minutes(dist),
        'waypoints': waypoints,
        'source': 'interpolated',
    }
