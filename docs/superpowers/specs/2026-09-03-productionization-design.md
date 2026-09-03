# Safar-e-Taleem Productionization — Design Spec

Date: 2026-09-03
Status: Approved (user chose "go all the way" — no further review gates)

## Goal

Close every gap identified in the project audit: real notification delivery
(Pakistani SMS gateway + WhatsApp Cloud API), real phone numbers, real
school-distance math, principal live map, real geocoding/routing (free,
keyless), offline map tiles, config hardening, dependency cleanup, and broad
test coverage. Demo behavior must keep working with zero configuration.

## 1. Notifications (`modules/notification.py`, rewrite)

Provider architecture with graceful fallback to the existing simulation:

- **SMS channel** — generic Pakistani HTTP SMS gateway adapter
  (SMS4Connect-style request shape). Configured via env:
  `SMS_GATEWAY_URL`, `SMS_GATEWAY_USERNAME`, `SMS_GATEWAY_PASSWORD`,
  `SMS_GATEWAY_SENDER`. Sends `requests.post` with 8s timeout; never raises.
- **WhatsApp channel** — Meta WhatsApp Cloud API. Env:
  `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`.
- **IVR channel** — simulated (documented provider hook).
- Env unset → simulation (current behavior preserved for demos).
- New `normalize_pk_phone(raw)` → E.164 (+92…) with 03XX / 92… / +92… inputs.
- Provider response status ('sent'/'queued'/'failed') flows into
  `NotificationLog.status`.

## 2. Phone numbers (`app.py`, `seed.py`, `register.html`)

- `User.phone` (String(20), nullable).
- Registration: optional phone input, `03XX-XXXXXXX` hint, JS auto-format.
- Seed users get fictional 03XX numbers.
- `ensure_schema_upgrades()`: SQLite `ALTER TABLE user ADD COLUMN phone`
  when missing (create_all does not migrate existing DBs).
- Notifications send to `user.phone` when present; CNIC-derived number only
  as a demo fallback.

## 3. School model + real distances (`app.py`, `seed.py`)

- New `School` model: `name` (unique), `latitude`, `longitude`.
  Seeded from `seed.py`'s existing `SCHOOLS` dict (7 schools).
- `get_school(name)` — case-insensitive lookup.
- `distance_to_school(user)` → haversine km or `None`.
- Replaces hardcoded `d = 2.5` in: principal avg monthly cost, parent
  dashboard `sample_distance`, Ask Ammi/Abba `db_context`.
- Registration `school_name` input gets a `<datalist>` of known schools.
- Maps render school markers (parent's school + all schools on principal).

## 4. Geo services (new `modules/geo_services.py`, keyless)

- `geocode(query)` → Nominatim
  (`/search?format=jsonv2&countrycodes=pk&limit=5`), User-Agent
  `Safar-e-Taleem/1.0`, 24h TTL cache, ≤8s timeout, returns
  `[{label, latitude, longitude}]`. Failure → `[]`.
- `walking_route(start, end)` → OSRM demo server
  (`router.project-osrm.org/route/v1/foot/…?overview=full&geometries=geojson`)
  → `{distance_km, duration_min, waypoints[[lat,lon],…]}`. Failure →
  straight-line interpolation between endpoints (10 evenly spaced points).
- Routes: `GET /api/geocode?q=`, `GET /api/route?start_lat&start_lon&end_lat&end_lon`.

## 5. Frontend

- **register.html** — "Search address" button beside the Address input;
  renders up to 5 geocode results as clickable chips that fill address +
  hidden lat/lon inputs. Phone field (auto-format). School datalist.
- **location.js** — hardcoded Bahria Phase 4 MOCK_ROUTE removed. On share
  start: fetch `/api/route` (home→school, school coords injected via
  `window.LIVE_LOCATION_SCHOOL`), draw route polyline + school marker, then
  step along the real route waypoints on each ping when GPS is unavailable.
- **principal.html + new static/js/school_map.js** — "Live Commute Map"
  card: Leaflet map polling `/api/location/pod` every 6s (principal already
  receives all active shares), green/amber(stale)/red(SOS) markers, school
  pins, auto-fit bounds. Sidebar nav link added.
- **sw.js** — `tile.openstreetmap.org` added to stale-while-revalidate
  cache hosts; `CACHE_NAME` version bumped (tiles now cached offline).

## 6. Config hardening + cleanup

- `app.py`: `load_dotenv()` before config (fixes .env SECRET_KEY/DASHSCOPE
  never applying to app config); `SECRET_KEY = env or secrets.token_hex(32)`
  with production warning when auto-generated; `DATABASE_URL` env override
  (default `sqlite:///database.db`) for Postgres on Render.
- `requirements.txt`: remove `folium` + `beautifulsoup4` (unused anywhere);
  add `psycopg2-binary`.
- `generate_addresses.py`: remove unused `import folium`.
- `.env.example` + `README.md`: document new env vars; refresh test count.

## 7. Tests (new, ~60 tests)

- `tests/test_notification.py` — dispatcher routing, unknown channel,
  provider env-gating with mocked `requests.post`, phone normalization,
  simulation fallback.
- `tests/test_geo_services.py` — geocode/route proxies with mocked
  requests, TTL cache, straight-line fallback.
- `tests/test_petrol_price.py` — fallback on network failure, payload
  parsing, cache TTL, wrapper shape.
- `tests/test_ai_responses.py` — `detect_intent`, rule-engine responses,
  `sanitize_roman_urdu_response`, `normalize_chat_history`.
- `tests/test_app_routes.py` — Flask test client on a temp DB: index,
  demo-login both roles, CSRF rejection, CNIC validation, petrol API shape,
  hybrid toggle permission, location start→ping→SOS→stop lifecycle,
  geocode/route endpoints (mocked), school seeding + distance helper.

## Constraints

- No API keys anywhere by default (project philosophy; maps stay
  Leaflet+OSM).
- Zero-config demo behavior unchanged (simulation fallbacks everywhere).
- No git commits unless the user explicitly asks.

## Verification

1. Python 3.12 via winget (background install already started).
2. venv + `pip install -r requirements.txt`.
3. Full pytest suite green.
4. Boot Flask server; browser-check parent + principal dashboards
   (registration geocode UI, live maps, route polyline).
