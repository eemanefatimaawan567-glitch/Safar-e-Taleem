"""
Safar-e-Taleem — Unit Tests for the Petrol Price Module
========================================================
Covers: offline fallback, server-side caching, and TrackMate response
parsing. All HTTP is mocked — tests never touch the network.
"""
import modules.petrol_price as petrol_module
from modules.petrol_price import (
    get_petrol_price,
    get_live_fuel_prices,
    DEFAULT_PETROL,
    DEFAULT_DIESEL,
    _fetch_trackmate,
)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.text = str(payload or '')
        self._payload = payload or {}

    def json(self):
        return self._payload


def _clear_cache():
    petrol_module._cache = None
    petrol_module._cache_ts = 0


# ============================================================
# 1. OFFLINE FALLBACK
# ============================================================
class TestOfflineFallback:
    def test_unreachable_api_returns_defaults(self, monkeypatch):
        """conftest disables the network — the module must fall back cleanly."""
        _clear_cache()
        result = get_live_fuel_prices()
        assert result['petrol'] == DEFAULT_PETROL
        assert result['diesel'] == DEFAULT_DIESEL
        assert result['source'] == 'fallback'

    def test_get_petrol_price_shape(self):
        """The dict consumed by app.py always has the required keys."""
        result = get_petrol_price()
        for key in ('price', 'current_price', 'diesel', 'kerosene', 'lpg',
                    'effective_date', 'source', 'checked_at'):
            assert key in result
        assert result['price'] > 0


# ============================================================
# 2. SERVER-SIDE CACHE (5-minute TTL)
# ============================================================
class TestCache:
    def test_fetch_called_once_within_ttl(self, monkeypatch):
        _clear_cache()
        calls = []

        def counting_fetch():
            calls.append(1)
            return {'petrol': 350.0, 'diesel': 360.0, 'kerosene': None,
                    'lpg': None, 'effective_date': None,
                    'source': 'test', 'checked_at': 'now'}

        monkeypatch.setattr(petrol_module, '_fetch_trackmate', counting_fetch)
        first = get_live_fuel_prices()
        second = get_live_fuel_prices()

        assert len(calls) == 1
        assert first['petrol'] == second['petrol'] == 350.0

    def test_cache_respects_ttl(self, monkeypatch):
        _clear_cache()
        calls = []

        def counting_fetch():
            calls.append(1)
            return {'petrol': 351.0, 'diesel': 361.0, 'kerosene': None,
                    'lpg': None, 'effective_date': None,
                    'source': 'test', 'checked_at': 'now'}

        monkeypatch.setattr(petrol_module, '_fetch_trackmate', counting_fetch)
        get_live_fuel_prices()

        # Simulate the cache expiring
        petrol_module._cache_ts -= (petrol_module.CACHE_TTL + 1)
        get_live_fuel_prices()

        assert len(calls) == 2


# ============================================================
# 3. TRACKMATE RESPONSE PARSING
# ============================================================
class TestFetchTrackmate:
    def _payload(self):
        return {
            'count': 4,
            'prices': [
                # National prices (city: null) — these are used
                {'source': 'pso', 'product': 'petrol', 'price_pkr': 342.02,
                 'unit': 'litre', 'city': None, 'effective_date': '29-August-2026'},
                {'source': 'shell', 'product': 'hsd', 'price_pkr': 371.5,
                 'unit': 'litre', 'city': None, 'effective_date': '29-August-2026'},
                {'source': 'pso', 'product': 'kerosene', 'price_pkr': 230.0,
                 'unit': 'litre', 'city': None, 'effective_date': None},
                # City-specific price — must be IGNORED
                {'source': 'pso', 'product': 'petrol', 'price_pkr': 345.0,
                 'unit': 'litre', 'city': 'Karachi', 'effective_date': None},
            ],
        }

    def test_parses_national_prices(self, monkeypatch):
        monkeypatch.setattr(petrol_module.requests, 'get',
                            lambda *a, **kw: _FakeResponse(200, self._payload()))
        result = _fetch_trackmate()
        assert result is not None
        assert result['petrol'] == 342.02
        assert result['diesel'] == 371.5
        assert result['kerosene'] == 230.0
        assert result['effective_date'] == '29-August-2026'

    def test_http_error_returns_none(self, monkeypatch):
        monkeypatch.setattr(petrol_module.requests, 'get',
                            lambda *a, **kw: _FakeResponse(503, {}))
        assert _fetch_trackmate() is None

    def test_empty_prices_returns_none(self, monkeypatch):
        monkeypatch.setattr(petrol_module.requests, 'get',
                            lambda *a, **kw: _FakeResponse(200, {'prices': []}))
        assert _fetch_trackmate() is None

    def test_missing_petrol_returns_none(self, monkeypatch):
        payload = {'prices': [
            {'source': 'pso', 'product': 'hsd', 'price_pkr': 371.5,
             'unit': 'litre', 'city': None, 'effective_date': None},
        ]}
        monkeypatch.setattr(petrol_module.requests, 'get',
                            lambda *a, **kw: _FakeResponse(200, payload))
        assert _fetch_trackmate() is None

    def test_network_exception_returns_none(self, monkeypatch):
        def exploding_get(*args, **kwargs):
            raise petrol_module.requests.ConnectionError('no internet')

        monkeypatch.setattr(petrol_module.requests, 'get', exploding_get)
        assert _fetch_trackmate() is None
