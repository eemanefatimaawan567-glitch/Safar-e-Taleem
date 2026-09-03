"""
Safar-e-Taleem — Shared pytest fixtures
========================================
Isolates the test run from the developer's real environment BEFORE the
Flask app is imported:

  • DATABASE_URL   → throwaway temp SQLite file (never touches instance/database.db)
  • API keys       → cleared so the AI/notification modules run in their
                     offline fallback modes (deterministic, no network)
  • RATE_LIMIT_DISABLED → on by default so tests aren't throttled
                     (the rate-limit test re-enables it via monkeypatch)
  • SSE_CYCLE_SECONDS = 0 → the location stream closes instantly in tests
  • SCHOOL_GEOCODING = 0  → school lookups use the offline registry only, so a
                     missing Nominatim reply can never change a test's numbers

The app auto-seeds demo users on first run, so every test session starts
with the standard demo families (Ayesha, Hassan, Sana, ...).
"""
import atexit
import os
import re
import shutil
import sys
import tempfile

import pytest

# --- must happen before any project import ---------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_TMP_DIR = tempfile.mkdtemp(prefix='safar-e-taleem-test-')
_DB_PATH = os.path.join(_TMP_DIR, 'test.db').replace(os.sep, '/')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_PATH}'
os.environ['FLASK_DEBUG'] = 'false'
os.environ['RATE_LIMIT_DISABLED'] = '1'
os.environ['SSE_CYCLE_SECONDS'] = '0'
os.environ['SCHOOL_GEOCODING'] = '0'

for _var in (
    'DASHSCOPE_API_KEY',
    'WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID',
    'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_FROM_NUMBER',
):
    os.environ.pop(_var, None)

import app as app_module  # noqa: E402  (import AFTER env is prepared)
import modules.petrol_price as _petrol_module  # noqa: E402


# Never hit the real TrackMate API from tests: make every outbound HTTP GET
# fail instantly so the petrol module serves its offline fallback defaults.
# (requests.post stays untouched — notification tests mock it per-test.)
def _no_network_get(*args, **kwargs):
    raise _petrol_module.requests.ConnectionError('network disabled in tests')


_petrol_module.requests.get = _no_network_get

# Remove the throwaway test database when the session ends.
atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)


@pytest.fixture()
def client():
    """Flask test client with a fresh session per test."""
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def get_csrf_token(client, url='/login'):
    """Fetch a form page and extract its CSRF token (per-session)."""
    response = client.get(url)
    match = re.search(r'name="_csrf_token" value="([^"]+)"',
                      response.get_data(as_text=True))
    assert match, f'No CSRF token found on {url}'
    return match.group(1)


def login(client, email, password):
    """Log in through the real form flow (with CSRF)."""
    token = get_csrf_token(client)
    return client.post('/login', data={
        'email': email,
        'password': password,
        '_csrf_token': token,
    }, follow_redirects=False)
