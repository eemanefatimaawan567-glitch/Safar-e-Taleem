# Safar-e-Taleem Productionization — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.
> NOTE: Workspace has no `.git` (downloaded archive) — skip all commit steps.

**Goal:** Close all audited gaps: real PK SMS/WhatsApp delivery, phone numbers, school-distance math, principal live map, keyless geocoding/routing, offline tiles, config hardening, dependency cleanup, full test coverage.

**Architecture:** Flask monolith preserved. New `modules/geo_services.py` (Nominatim + OSRM proxies). `modules/notification.py` rewritten as provider layer (PK HTTP SMS gateway + Meta WhatsApp Cloud API + simulation fallback). `app.py` gains `School` model, `User.phone`, schema migration helper, real-distance math, two new API endpoints. Frontend: dynamic OSRM route in `location.js`, new `school_map.js` for principal, geocode UI in `register.html`, OSM tile caching in `sw.js`.

**Tech Stack:** Python 3.12, Flask, SQLAlchemy, requests, Leaflet 1.9.3, Nominatim, OSRM, pytest.

---

### Task 1: Environment setup

- [ ] Install Python 3.12 via winget (background terminal already running)
- [ ] Locate python.exe, create venv at project root: `python -m venv .venv`
- [ ] `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- [ ] Run existing suite: `.venv\Scripts\python.exe -m pytest tests -q` → 32 pass baseline

### Task 2: `modules/geo_services.py` (TDD)

**Files:** Create `modules/geo_services.py`, `tests/test_geo_services.py`

- [ ] Write tests: geocode parses Nominatim JSON (mock `requests.get`), caches result (2nd call = 0 HTTP hits), returns `[]` on network error, `[]` for short queries; `walking_route` parses OSRM geojson (distance_km/duration_min/waypoints/source='osrm'), falls back to interpolated straight line (10 waypoints, endpoints preserved, source='interpolated') when OSRM fails.
- [ ] Implement module (full code in this plan, section A)
- [ ] `pytest tests/test_geo_services.py -q` → PASS

### Task 3: `modules/notification.py` provider rewrite (TDD)

**Files:** Rewrite `modules/notification.py`, create `tests/test_notification.py`

- [ ] Write tests: `normalize_pk_phone` ('03001234567'→'+923001234567', '+923001234567' unchanged, '923001234567'→'+923001234567', '0300 123 4567'→'+923001234567', ''→''); unknown channel → error dict; simulation fallback when env unset (WA/SMS/IVR message_id prefixes, status 'delivered'); real SMS gateway path with mocked `requests.post` (receiver normalized, status 'sent'); WhatsApp Cloud path with mocked post ('queued'/'sent' + wamid); provider exception → status 'failed', never raises.
- [ ] Implement (full code in plan, section B) — env read at call time (not import) so tests can toggle
- [ ] `pytest tests/test_notification.py -q` → PASS

### Task 4: `app.py` core — config, models, migration, seeding

**Files:** Modify `app.py`, `seed.py`

- [ ] Top of app.py: `from dotenv import load_dotenv; load_dotenv()` before Flask init; SECRET_KEY = env or `secrets.token_hex(32)` (warn in prod); `SQLALCHEMY_DATABASE_URI` from `DATABASE_URL` env (default sqlite)
- [ ] `User.phone = db.Column(db.String(20), default='')`
- [ ] New `School` model (name unique, latitude, longitude)
- [ ] `ensure_schema_upgrades()` — SQLite-only ALTER TABLE adding `phone` to existing user table
- [ ] Seed `School` rows from `seed.SCHOOLS` on startup (7 schools) in the init block and in `seed()`
- [ ] `seed.py`: add `phone` to all DEMO_USERS (fictional 03XX numbers)
- [ ] Helpers: `get_school(name)` (case-insensitive), `distance_to_school(user)` → km or None

### Task 5: `app.py` routes — new APIs + real distances + phone

- [ ] `GET /api/geocode?q=` → `{'results': geocode(q)}` (public — registration is pre-login)
- [ ] `GET /api/route?start_lat&start_lon&end_lat&end_lon` → walking_route dict (public, 400 on bad params)
- [ ] `register()`: capture + validate optional phone (Pakistani mobile regex); pass `schools` list to template
- [ ] `parent_dashboard()`: `sample_distance = distance_to_school(user) or 2.5` (removes cluster-avg proxy); pass `school` object
- [ ] `principal_dashboard()`: per-parent `d = distance_to_school(u) or 2.5` in avg cost; pass `schools` list
- [ ] `ask_ammi_abba()`: `db_context['school_distance_km']`
- [ ] `notify_pod()` + `broadcast_curriculum()`: `member.phone or member.cnic.replace('-','')`

### Task 6: `tests/test_app_routes.py`

- [ ] Module fixture: temp-file DATABASE_URL, SECRET_KEY, stub `app.fetch_live_petrol_price` (no network), import app once, yield test_client
- [ ] Tests: index 200 + metrics present; demo-login parent/principal redirect to dashboards; login CSRF 403 without token, 200-flow with token; register rejects bad CNIC, accepts good (phone stored); /api/petrol-price shape; hybrid toggle 403 as parent; location lifecycle start→ping→sos→pod(is_sos)→stop; geocode/route endpoints with mocked `app.geocode`/`app.walking_route`; School seeded (7), get_school case-insensitive, distance_to_school(ayesha) ≈ 0.78 km
- [ ] `pytest tests/test_app_routes.py -q` → PASS

### Task 7: `tests/test_petrol_price.py` + `tests/test_ai_responses.py`

- [ ] petrol: `_fetch_trackmate` parses sample payload (national petrol/hsd/kerosene/lpg, skips city rows); fallback defaults when fetch returns None; 5-min cache prevents second fetch; `get_petrol_price()` wrapper shape
- [ ] ai_responses: `detect_intent` routing (price/carpool/walking/savings/nearby/default); rule-engine output includes user first name + petrol price; `sanitize_roman_urdu_response` fixes banned spellings; `normalize_chat_history` caps turns/length, drops malformed
- [ ] `pytest tests/test_petrol_price.py tests/test_ai_responses.py -q` → PASS

### Task 8: `register.html` — phone, geocode search, school datalist

- [ ] Phone field (auto-format 03XX-XXXXXXX via JS) between CNIC and Email
- [ ] Address row: "Search" button → `searchAddress()` → `/api/geocode` → up to 5 result chips → click fills address + hidden lat/lon + success hint
- [ ] `school_name` input + `<datalist id="school-list">` from `{{ schools }}`

### Task 9: `location.js` + `parent.html` — dynamic route

- [ ] parent.html: inject `window.LIVE_LOCATION_SCHOOL` (school coords or null)
- [ ] location.js: delete MOCK_ROUTE; add `loadRoute()` (fetch `/api/route` home→school, fallback `interpolate()`), draw dashed polyline + school marker on init; `simulatePosition()` steps along `routeWaypoints` (step size = `floor(len/9)` min 1); GPS path unchanged; reset on stop

### Task 10: Principal live map

**Files:** Create `static/js/school_map.js`, modify `templates/principal.html`

- [ ] principal.html: Leaflet CSS/JS includes; `window.SCHOOL_LOCATIONS` injection; new "Live Commute Map" `panel-card` (map div + legend) after the SOS banner; sidebar nav link
- [ ] school_map.js: init map on first school, school pins, poll `/api/location/pod` every 6s, color markers (green/amber stale/red SOS) mirroring location.js, auto-fit bounds, empty-state handling

### Task 11: `sw.js` — offline tiles + cleanup files

- [ ] Add `'tile.openstreetmap.org'` to CDN_HOSTS array; bump CACHE_NAME version
- [ ] `requirements.txt`: remove `folium`, `beautifulsoup4`; add `psycopg2-binary>=2.9.9`
- [ ] `generate_addresses.py`: remove unused `import folium`
- [ ] `.env.example`: DATABASE_URL, SMS_GATEWAY_*, WHATSAPP_* docs
- [ ] `README.md`: env table + test count refresh

### Task 12: Full verification

- [ ] `pytest tests -q` → all green (32 old + ~60 new)
- [ ] Boot `python app.py`; browser-verify: register page (geocode search, phone, datalist), parent dashboard (route polyline + school pin + sharing), principal dashboard (live map card renders, no console errors)
- [ ] Kill server, report results

---

## Section A — `modules/geo_services.py` (reference implementation)

```python
import logging
import time
import requests
from modules.commute_engine import distance_km

logger = logging.getLogger('safar-e-taleem.geo')

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OSRM_URL = 'https://router.project-osrm.org/route/v1/foot/{start};{end}'
USER_AGENT = 'Safar-e-Taleem/1.0 (school-transport; contact: demo@example.com)'
GEOCODE_TTL = 24 * 3600

_geocode_cache = {}  # query -> (ts, results)


def geocode(query, limit=5):
    """Address -> coordinates via Nominatim (Pakistan-restricted, 24h cache)."""
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
        logger.warning('Nominatim returned HTTP %s', resp.status_code)
    except Exception as e:
        logger.warning('Geocode failed: %s', e)
    return []


def _interpolate(start_lat, start_lon, end_lat, end_lon, points=10):
    return [
        [round(start_lat + (end_lat - start_lat) * i / (points - 1), 6),
         round(start_lon + (end_lon - start_lon) * i / (points - 1), 6)]
        for i in range(points)
    ]


def walking_route(start_lat, start_lon, end_lat, end_lon):
    """Walking route via OSRM demo server; straight-line fallback."""
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
        'duration_min': round(dist / 4.5 * 60),  # ~4.5 km/h walking pace
        'waypoints': waypoints,
        'source': 'interpolated',
    }
```

## Section B — `modules/notification.py` (reference implementation)

```python
"""
Safar-e-Taleem — Curriculum Delivery (SMS / WhatsApp / IVR)

Channel routing with real providers when configured, simulation otherwise:
  • SMS:       any Pakistani HTTP SMS gateway (SMS4Connect-style request shape)
               via SMS_GATEWAY_URL / _USERNAME / _PASSWORD / _SENDER
  • WhatsApp:  Meta WhatsApp Cloud API via WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID
  • IVR:       simulated (plug a Twilio/Infobip/local provider into send_ivr)

Env vars are read at call time so the app can be reconfigured per request.
All senders return a dict and never raise.
"""
import os
import re
import logging
from datetime import datetime
import requests

logger = logging.getLogger('safar-e-taleem.notify')

WHATSAPP_GRAPH_URL = 'https://graph.facebook.com/v18.0/{phone_id}/messages'


def normalize_pk_phone(raw):
    """Normalize a Pakistani mobile number to E.164 (+92XXXXXXXXXX)."""
    digits = re.sub(r'\D', '', str(raw or ''))
    if not digits:
        return ''
    if digits.startswith('92'):
        return '+' + digits
    if digits.startswith('0'):
        return '+92' + digits[1:]
    return '+' + digits


def _configured(*keys):
    return all(os.getenv(k, '').strip() for k in keys)


def _simulated(prefix, preview):
    return {
        'status': 'delivered',
        'message_id': f'{prefix}{datetime.now().strftime("%Y%m%d%H%M%S%f")}',
        'preview': preview,
        'provider': 'simulated',
    }


def send_sms(phone, content_preview):
    """SMS via Pakistani HTTP gateway (SMS4Connect-style), else simulated."""
    if _configured('SMS_GATEWAY_URL', 'SMS_GATEWAY_USERNAME', 'SMS_GATEWAY_PASSWORD'):
        try:
            resp = requests.post(
                os.getenv('SMS_GATEWAY_URL'),
                data={
                    'user': os.getenv('SMS_GATEWAY_USERNAME'),
                    'pwd': os.getenv('SMS_GATEWAY_PASSWORD'),
                    'sender': os.getenv('SMS_GATEWAY_SENDER', 'SafarTaleem'),
                    'receiver': normalize_pk_phone(phone),
                    'text': content_preview[:480],
                },
                timeout=8,
            )
            body = (resp.text or '')[:200]
            ok = resp.status_code == 200 and 'error' not in body.lower()
            return {
                'status': 'sent' if ok else 'failed',
                'message_id': f'SMSGW{datetime.now().strftime("%Y%m%d%H%M%S%f")}',
                'preview': body,
                'provider': 'sms-gateway',
            }
        except Exception as e:
            logger.warning('SMS gateway error: %s', e)
            return {'status': 'failed', 'message_id': '', 'preview': str(e)[:200], 'provider': 'sms-gateway'}
    return _simulated('SMS', f'📱 {content_preview[:100]}')


def send_whatsapp(phone, content_preview):
    """WhatsApp via Meta Cloud API, else simulated."""
    if _configured('WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID'):
        try:
            resp = requests.post(
                WHATSAPP_GRAPH_URL.format(phone_id=os.getenv('WHATSAPP_PHONE_NUMBER_ID')),
                headers={'Authorization': f'Bearer {os.getenv("WHATSAPP_TOKEN")}'},
                json={
                    'messaging_product': 'whatsapp',
                    'to': normalize_pk_phone(phone),
                    'type': 'text',
                    'text': {'body': content_preview[:1024]},
                },
                timeout=8,
            )
            data = resp.json() if resp.content else {}
            msg_id = (data.get('messages') or [{}])[0].get('id', '')
            return {
                'status': 'sent' if resp.status_code == 200 else 'failed',
                'message_id': msg_id,
                'preview': f'📚 {content_preview[:150]}',
                'provider': 'whatsapp-cloud',
            }
        except Exception as e:
            logger.warning('WhatsApp Cloud error: %s', e)
            return {'status': 'failed', 'message_id': '', 'preview': str(e)[:200], 'provider': 'whatsapp-cloud'}
    return _simulated('WA', f'📚 {content_preview[:150]}')


def send_ivr(phone, content_preview):
    """IVR voice call — simulated until a voice provider is chosen."""
    return _simulated('IVR', f'📞 {content_preview[:120]}')


CHANNELS = {'whatsapp': send_whatsapp, 'sms': send_sms, 'ivr': send_ivr}


def send_notification(channel, phone, content_preview):
    sender = CHANNELS.get(channel)
    if not sender:
        return {'status': 'error', 'message': f'Unknown channel: {channel}'}
    return sender(phone, content_preview)
```

## Self-Review

- **Spec coverage:** notifications (T3), phone (T4/T5/T8), schools+distances (T4/T5), geo APIs (T2/T5), register UI (T8), parent route (T9), principal map (T10), tiles+cleanup (T11), tests (T2/T3/T6/T7), config (T4), verification (T12). No gaps.
- **Placeholders:** none — greenfield code complete; edit tasks specify exact functions and logic.
- **Type consistency:** `send_notification(channel, phone, preview)` signature unchanged for app.py callers; `geocode`/`walking_route` names match Task 5 imports; `School.latitude/longitude` used by both map injections.
