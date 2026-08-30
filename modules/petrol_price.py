import logging
import time
import requests
from datetime import datetime

logger = logging.getLogger('safar-e-taleem.petrol')

# Fallback prices if the API is unreachable
DEFAULT_PETROL = 343.00
DEFAULT_DIESEL = 371.00

# Module-level cache — avoids hammering the external API.
# The cache is invalidated after CACHE_TTL seconds.
_cache = None
_cache_ts = 0
CACHE_TTL = 300  # 5 minutes

_API_URL = "https://fuel.trackmate.page/api/prices"


def _fetch_trackmate():
    """
    Fetches live fuel prices from the TrackMate Pakistan fuel-price API.
    Returns a dict with petrol, diesel, kerosene, lpg prices, effective date,
    and source information.  Returns None on any failure.

    API response shape (inspected Aug 2026):
    {
        "count": 26,
        "prices": [
            {
                "source": "pakwheels" | "pso" | "shell",
                "product": "petrol" | "hsd" | "kerosene" | "lpg" | "lsd" | "octane_plus",
                "price_pkr": 342.02,
                "unit": "litre" | "kg",
                "city": null | "Karachi" | ...,
                "effective_date": "29-August-2026" | null,
                "scraped_at": "2026-08-29T04:00:25.353Z"
            }
        ]
    }
    """
    try:
        response = requests.get(_API_URL, timeout=8, headers={
            "User-Agent": "Safar-e-Taleem/1.0",
            "Accept": "application/json",
        })
        if response.status_code != 200:
            logger.warning('TrackMate API returned HTTP %s. Using fallback.', response.status_code)
            return None

        data = response.json()
        prices = data.get('prices', [])
        if not prices:
            logger.warning('TrackMate API returned empty prices list. Using fallback.')
            return None

        # Extract prices — prefer the first match per product (national price)
        petrol_price = None
        diesel_price = None
        kerosene_price = None
        lpg_price = None
        effective_date = None
        source_names = set()

        for item in prices:
            product = (item.get('product') or '').lower().strip()
            price = item.get('price_pkr')
            src = item.get('source', '')
            eff = item.get('effective_date')

            if price is None:
                continue

            # Only take national prices (city is null) to avoid per-city duplicates
            if item.get('city') is not None:
                continue

            source_names.add(src)

            if eff:
                effective_date = eff

            if product == 'petrol' and petrol_price is None:
                petrol_price = float(price)
            elif product == 'hsd' and diesel_price is None:
                diesel_price = float(price)
            elif product == 'kerosene' and kerosene_price is None:
                kerosene_price = float(price)
            elif product == 'lpg' and lpg_price is None:
                lpg_price = float(price)

        if petrol_price is None:
            logger.warning('TrackMate API: no national petrol price found. Using fallback.')
            return None

        return {
            'petrol': petrol_price,
            'diesel': diesel_price or DEFAULT_DIESEL,
            'kerosene': kerosene_price,
            'lpg': lpg_price,
            'effective_date': effective_date,
            'source': 'TrackMate (' + ', '.join(sorted(source_names)) + ')' if source_names else 'TrackMate API',
            'checked_at': datetime.now().isoformat(),
        }

    except requests.Timeout:
        logger.warning('TrackMate API timed out (>8s). Using fallback.')
    except requests.ConnectionError:
        logger.warning('No internet connection to TrackMate API. Using fallback.')
    except (ValueError, KeyError) as e:
        logger.warning('TrackMate API parse error: %s. Using fallback.', e)
    except Exception as e:
        logger.warning('TrackMate API unexpected error: %s. Using fallback.', e)

    return None


def get_live_fuel_prices():
    """
    Returns live fuel prices with a 5-minute server-side cache.
    Falls back to defaults if the API is unreachable.
    Always returns a dict — never raises.
    """
    global _cache, _cache_ts

    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL:
        return _cache

    result = _fetch_trackmate()

    if result is None:
        result = {
            'petrol': DEFAULT_PETROL,
            'diesel': DEFAULT_DIESEL,
            'kerosene': None,
            'lpg': None,
            'effective_date': None,
            'source': 'fallback',
            'checked_at': datetime.now().isoformat(),
        }

    _cache = result
    _cache_ts = now
    return result


# ----------------------------------------------------------------
# Backward-compatible wrappers (used by app.py get_tracked_petrol_price)
# ----------------------------------------------------------------

def get_petrol_price():
    """
    Returns the dict expected by app.py's get_tracked_petrol_price().
    Includes diesel and extra fuel-type data for the frontend.
    """
    fuel = get_live_fuel_prices()
    return {
        "price": fuel['petrol'],
        "current_price": fuel['petrol'],
        "diesel": fuel['diesel'],
        "kerosene": fuel.get('kerosene'),
        "lpg": fuel.get('lpg'),
        "effective_date": fuel.get('effective_date'),
        "source": fuel['source'],
        "checked_at": fuel['checked_at'],
    }


def get_current_price():
    return get_petrol_price()
