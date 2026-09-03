"""Tests for modules/geo_services.py — Nominatim geocoding + OSRM routing proxies."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import requests

from modules import geo_services


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clear_geocode_cache():
    geo_services._geocode_cache.clear()
    yield
    geo_services._geocode_cache.clear()


class TestGeocode:
    def test_parses_nominatim_results(self, monkeypatch):
        payload = [
            {'display_name': 'G-11, Islamabad, Pakistan', 'lat': '33.6789', 'lon': '72.9744'},
            {'display_name': 'G-11 Markaz, Islamabad', 'lat': '33.6810', 'lon': '72.9760'},
        ]
        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append(params)
            return FakeResponse(payload=payload)

        monkeypatch.setattr(geo_services.requests, 'get', fake_get)
        results = geo_services.geocode('G-11 Islamabad')

        assert len(results) == 2
        assert results[0]['label'] == 'G-11, Islamabad, Pakistan'
        assert results[0]['latitude'] == pytest.approx(33.6789)
        assert results[0]['longitude'] == pytest.approx(72.9744)
        assert calls[0]['countrycodes'] == 'pk'

    def test_caches_results(self, monkeypatch):
        calls = []

        def fake_get(url, params=None, headers=None, timeout=None):
            calls.append(params)
            return FakeResponse(payload=[{'display_name': 'x', 'lat': '1.0', 'lon': '2.0'}])

        monkeypatch.setattr(geo_services.requests, 'get', fake_get)
        geo_services.geocode('Satellite Town Rawalpindi')
        geo_services.geocode('Satellite Town Rawalpindi')
        assert len(calls) == 1

    def test_network_error_returns_empty(self, monkeypatch):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise requests.ConnectionError('down')

        monkeypatch.setattr(geo_services.requests, 'get', fake_get)
        assert geo_services.geocode('Bahria Town') == []

    def test_http_error_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            geo_services.requests, 'get',
            lambda url, params=None, headers=None, timeout=None: FakeResponse(status_code=503),
        )
        assert geo_services.geocode('Bahria Town') == []

    def test_short_query_skips_network(self, monkeypatch):
        def boom(url, params=None, headers=None, timeout=None):
            raise AssertionError('should not hit network')

        monkeypatch.setattr(geo_services.requests, 'get', boom)
        assert geo_services.geocode('ab') == []
        assert geo_services.geocode('') == []
        assert geo_services.geocode(None) == []

    def test_skips_rows_without_coords(self, monkeypatch):
        payload = [
            {'display_name': 'ok', 'lat': '1.0', 'lon': '2.0'},
            {'display_name': 'no coords'},
        ]
        monkeypatch.setattr(
            geo_services.requests, 'get',
            lambda url, params=None, headers=None, timeout=None: FakeResponse(payload=payload),
        )
        results = geo_services.geocode('somewhere pakistan')
        assert len(results) == 1


class TestWalkingRoute:
    def test_parses_osrm_response(self, monkeypatch):
        payload = {
            'routes': [{
                'distance': 1200.0,
                'duration': 900.0,
                'geometry': {'coordinates': [[72.9744, 33.6789], [72.9760, 33.6800], [72.9800, 33.6840]]},
            }]
        }
        monkeypatch.setattr(
            geo_services.requests, 'get',
            lambda url, params=None, headers=None, timeout=None: FakeResponse(payload=payload),
        )
        route = geo_services.walking_route(33.6789, 72.9744, 33.6840, 72.9800)

        assert route['source'] == 'osrm'
        assert route['distance_km'] == pytest.approx(1.2)
        # Duration is derived from distance at WALKING_SPEED_KMH (1.2 km -> 16
        # min), not copied from OSRM's 900 s. See the next test for why.
        assert route['duration_min'] == 16
        assert route['waypoints'] == [[33.6789, 72.9744], [33.6800, 72.9760], [33.6840, 72.9800]]

    def test_osrm_driving_duration_is_replaced_with_walking_pace(self, monkeypatch):
        """The public OSRM demo server ignores the profile segment and answers
        EVERY request with its car routing -- verified by requesting 'foot',
        'driving', 'bike' and nonsense profiles for one coordinate pair and
        getting byte-identical results (1.53 km in 3.1 min = 29 km/h).

        The geometry is still worth keeping because it follows real roads, but
        the duration is a driving time. Reporting it as a walk would tell a
        parent that 1.5 km takes 3 minutes.
        """
        payload = {'routes': [{
            'distance': 1530.0,      # real road distance
            'duration': 186.0,       # 3.1 min == 29 km/h: a car, not a child
            'geometry': {'coordinates': [[73.1543, 33.5348], [73.1600, 33.5400]]},
        }]}
        monkeypatch.setattr(
            geo_services.requests, 'get',
            lambda url, params=None, headers=None, timeout=None: FakeResponse(payload=payload),
        )
        route = geo_services.walking_route(33.5348, 73.1543, 33.5400, 73.1600)

        assert route['source'] == 'osrm'
        assert route['distance_km'] == pytest.approx(1.53)
        assert route['duration_min'] == 20              # 1.53 km at 4.5 km/h
        assert route['duration_min'] != round(186 / 60)  # ...not the car's 3 min

    def test_both_sources_quote_the_same_walking_pace(self):
        """A routed path and a straight-line path must not disagree about pace,
        or the map readout changes meaning when the network drops."""
        assert geo_services.WALKING_SPEED_KMH == 4.5
        assert geo_services._walking_minutes(4.5) == 60
        assert geo_services._walking_minutes(1.53) == 20
        assert geo_services._walking_minutes(0.0) == 1   # never a "0 min walk"

    def test_osrm_failure_falls_back_to_interpolation(self, monkeypatch):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise requests.Timeout('osrm down')

        monkeypatch.setattr(geo_services.requests, 'get', fake_get)
        route = geo_services.walking_route(33.5348, 73.1543, 33.5400, 73.1600)

        assert route['source'] == 'interpolated'
        assert len(route['waypoints']) == 10
        assert route['waypoints'][0] == [pytest.approx(33.5348), pytest.approx(73.1543)]
        assert route['waypoints'][-1] == [pytest.approx(33.5400), pytest.approx(73.1600)]
        assert route['distance_km'] == pytest.approx(0.78, abs=0.05)

    def test_malformed_osrm_payload_falls_back(self, monkeypatch):
        monkeypatch.setattr(
            geo_services.requests, 'get',
            lambda url, params=None, headers=None, timeout=None: FakeResponse(payload={'routes': []}),
        )
        route = geo_services.walking_route(0.0, 0.0, 1.0, 1.0)
        assert route['source'] == 'interpolated'

    def test_interpolated_duration_estimated_at_walking_pace(self, monkeypatch):
        def fake_get(url, params=None, headers=None, timeout=None):
            raise requests.ConnectionError('down')

        monkeypatch.setattr(geo_services.requests, 'get', fake_get)
        route = geo_services.walking_route(0.0, 0.0, 0.045, 0.0)  # ~5 km north
        assert route['distance_km'] == pytest.approx(5.0, abs=0.2)
        assert route['duration_min'] == pytest.approx(
            5.0 / geo_services.WALKING_SPEED_KMH * 60, abs=2)
