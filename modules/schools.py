"""
Safar-e-Taleem — School Coordinate Registry & commute distance
==============================================================
`recommend_transport()` chooses between a Supervised Walking Group, Shared
Transport, Carpool or Individual Transport based on the HOME -> SCHOOL
distance. The dashboards used to feed it the DBSCAN *cluster spread* (how far
neighbours live from each other), so a family 8 km from school who happened to
live next to two neighbours was told to walk. This module resolves real school
coordinates so the engine receives the distance it actually expects.

Resolution order — cheapest first, and never raises:
  1. Built-in registry (demo schools, keyed by school name AND neighbourhood)
  2. OpenStreetMap Nominatim via modules.geo_services (24 h server-side cache;
     set SCHOOL_GEOCODING=0 to disable, e.g. offline or in tests)
  3. None -> callers fall back to DEFAULT_COMMUTE_KM

Every answer (hit or miss) is memoised in `_resolved` so a school we cannot
place is looked up once per process, never once per dashboard render.
"""
import os

from modules.commute_engine import distance_km
from modules.geo_services import geocode

# Used when a family's school cannot be placed on the map — the same neutral
# 2.5 km the dashboards assumed before, kept so nothing silently becomes 0.
DEFAULT_COMMUTE_KM = 2.5

# Anything beyond this is a data-entry mistake (school in another city) rather
# than a real commute, so we prefer the default over a 300 km fuel estimate.
MAX_PLAUSIBLE_COMMUTE_KM = 60.0


# ---------------------------------------------------------
# REGISTRY — fictional demo schools, one per seeded neighbourhood
# ---------------------------------------------------------
# Same shape seed.py has always used (neighbourhood -> school), now the single
# source of truth for both seeding and runtime distance maths.
SCHOOLS = {
    "Bahria Town Phase 8": {
        "name": "Beaconhouse Bahria Town",
        "lat": 33.5400, "lon": 73.1600,
    },
    "G-11 Islamabad": {
        "name": "City School G-11",
        "lat": 33.6840, "lon": 72.9800,
    },
    "F-8 Islamabad": {
        "name": "Roots Millennium F-8",
        "lat": 33.7140, "lon": 73.0450,
    },
    "Satellite Town Rwp": {
        "name": "Allied School Satellite Town",
        "lat": 33.6300, "lon": 73.0500,
    },
    "DHA Phase 2": {
        "name": "LGS DHA Phase 2",
        "lat": 33.6150, "lon": 73.0950,
    },
    "Gulberg Lahore": {
        "name": "Beaconhouse Gulberg",
        "lat": 31.5200, "lon": 74.3500,
    },
    "Clifton Karachi": {
        "name": "Convent of Jesus & Mary",
        "lat": 24.8100, "lon": 67.0350,
    },
}


def _key(value):
    return (value or '').strip().lower()


# Two lookup tables so a caller can resolve by either the school's name or the
# family's neighbourhood — registration only guarantees one of the two.
_BY_SCHOOL_NAME = {_key(s['name']): (s['lat'], s['lon']) for s in SCHOOLS.values()}
_BY_NEIGHBORHOOD = {_key(area): (s['lat'], s['lon']) for area, s in SCHOOLS.items()}

# lookup key -> (lat, lon) | None   (None is cached too: a negative answer)
_resolved = {}


def _geocoding_enabled():
    return os.getenv('SCHOOL_GEOCODING', '1').strip().lower() not in ('0', 'false', 'no', 'off')


def _geocode_school(label):
    """Ask Nominatim for a school we don't know. Returns (lat, lon) or None."""
    if not _geocoding_enabled():
        return None
    # geo_services already restricts results to Pakistan and never raises.
    results = geocode(f'{label}, Pakistan', limit=1)
    if results:
        return (results[0]['latitude'], results[0]['longitude'])
    return None


def get_school_coords(school_name=None, neighborhood=None):
    """Resolve a school's coordinates, or None when it cannot be placed.

    Tries the registry by school name, then by neighbourhood, then a loose
    substring match (handles "Beaconhouse, Bahria Town" style free text),
    then Nominatim. Results — including failures — are memoised.
    """
    school_key = _key(school_name)
    area_key = _key(neighborhood)
    cache_key = f'{school_key}|{area_key}'

    if cache_key in _resolved:
        return _resolved[cache_key]

    coords = None
    if school_key and school_key in _BY_SCHOOL_NAME:
        coords = _BY_SCHOOL_NAME[school_key]
    elif area_key and area_key in _BY_NEIGHBORHOOD:
        coords = _BY_NEIGHBORHOOD[area_key]
    elif school_key:
        # Loose match: registered free-text names often wrap a known brand,
        # e.g. "Beaconhouse School, Gulberg" -> "Beaconhouse Gulberg".
        for known, known_coords in _BY_SCHOOL_NAME.items():
            if known in school_key or school_key in known:
                coords = known_coords
                break

    if coords is None:
        coords = _geocode_school(school_name or neighborhood or '')

    _resolved[cache_key] = coords
    return coords


def home_to_school_km(user):
    """Haversine distance (km) from a family's home to their school.

    Returns None when the user has no GPS coordinates or the school cannot be
    placed — callers decide what to do with an unknown commute.
    """
    if user is None:
        return None
    lat = getattr(user, 'latitude', None)
    lon = getattr(user, 'longitude', None)
    if not lat or not lon:
        return None

    coords = get_school_coords(getattr(user, 'school_name', None),
                               getattr(user, 'neighborhood', None))
    if not coords:
        return None

    km = distance_km(lat, lon, coords[0], coords[1])
    if km > MAX_PLAUSIBLE_COMMUTE_KM:
        return None
    return round(km, 2)


def commute_distance_km(user):
    """Always-numeric home->school commute, falling back to DEFAULT_COMMUTE_KM.

    This is the value the fuel-cost and transport-recommendation maths should
    use everywhere in the app.
    """
    km = home_to_school_km(user)
    if km is None:
        return DEFAULT_COMMUTE_KM
    # A school next door is still a real (short) commute — only floor it just
    # enough to avoid a divide-by-zero style "0 km, 0 rupees" dead end.
    return max(km, 0.1)


def school_info(user):
    """Everything the dashboard/map needs about a family's school.

    Returns {'name', 'latitude', 'longitude', 'distance_km', 'source'} or None
    when the school cannot be placed. `source` is 'registry' or 'geocoded' so
    the UI can be honest about where the pin came from.
    """
    if user is None:
        return None
    school_name = getattr(user, 'school_name', '') or ''
    neighborhood = getattr(user, 'neighborhood', '') or ''
    coords = get_school_coords(school_name, neighborhood)
    if not coords:
        return None

    registry_hit = (
        _key(school_name) in _BY_SCHOOL_NAME
        or _key(neighborhood) in _BY_NEIGHBORHOOD
    )
    info = {
        'name': school_name or (neighborhood and f'School in {neighborhood}') or 'School',
        'latitude': coords[0],
        'longitude': coords[1],
        'source': 'registry' if registry_hit else 'geocoded',
    }

    lat = getattr(user, 'latitude', None)
    lon = getattr(user, 'longitude', None)
    if lat and lon:
        km = distance_km(lat, lon, coords[0], coords[1])
        info['distance_km'] = round(km, 2) if km <= MAX_PLAUSIBLE_COMMUTE_KM else None
    else:
        info['distance_km'] = None
    return info
