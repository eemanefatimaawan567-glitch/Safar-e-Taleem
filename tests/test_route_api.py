"""
Safar-e-Taleem — Tests for the routing / geocoding endpoints
=============================================================
`modules/geo_services.py` shipped for a long time as dead code: 131 lines of
Nominatim + OSRM plumbing that nothing called, while the parent map drew
straight-line markers. These tests pin the two endpoints that finally expose it
(`/api/route`, `/api/geocode`) and the contract the Leaflet polyline depends on.

conftest disables all outbound HTTP, so OSRM is never reachable here and every
route comes back with source='interpolated' — which is itself worth asserting,
because that fallback is what keeps an offline demo drawing a line instead of an
empty map.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from modules.commute_engine import distance_km
from tests.conftest import login


AYESHA = 'ayesha@demo.com'
PRINCIPAL = 'principal@demo.com'
DEMO_PASSWORD = 'demo123'

# Seeded home pin and the registered school it commutes to (modules/schools.py)
AYESHA_HOME = (33.5348, 73.1543)
BAHRIA_SCHOOL = (33.5400, 73.1600)


class FakeUser:
    """Stand-in used to exercise branches the seeded accounts can't reach."""

    def __init__(self, latitude=None, longitude=None,
                 school_name=None, neighborhood=None):
        self.latitude = latitude
        self.longitude = longitude
        self.school_name = school_name
        self.neighborhood = neighborhood


@pytest.fixture(autouse=True)
def _no_school_geocoding(monkeypatch):
    """Keep resolution on the offline registry so no test depends on Nominatim."""
    monkeypatch.setenv('SCHOOL_GEOCODING', '0')
    import modules.schools as schools
    schools._resolved.clear()
    yield
    schools._resolved.clear()


def _login(client, email=AYESHA):
    response = login(client, email, DEMO_PASSWORD)
    assert response.status_code == 302, 'demo login should succeed'
    return response


# ============================================================
# 1. AUTHORIZATION
# ============================================================
class TestRouteAuthorization:
    def test_anonymous_is_redirected_to_login(self, client):
        response = client.get('/api/route?to=school')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/login')

    def test_anonymous_with_explicit_coordinates_is_also_redirected(self, client):
        # Explicit coords must not become a way to skip the session check.
        response = client.get('/api/route?start_lat=33.5&start_lon=73.1'
                              '&end_lat=33.6&end_lon=73.2')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/login')


# ============================================================
# 2. HOME -> SCHOOL ROUTE (what the map actually draws)
# ============================================================
class TestRouteToSchool:
    def test_returns_a_drawable_polyline(self, client):
        _login(client)
        data = client.get('/api/route?to=school').get_json()

        assert data['source'] == 'interpolated'   # OSRM unreachable in tests
        assert len(data['waypoints']) >= 2
        for point in data['waypoints']:
            assert isinstance(point, list) and len(point) == 2
            assert -90 <= point[0] <= 90
            assert -180 <= point[1] <= 180

    def test_polyline_starts_at_home_and_ends_at_school(self, client):
        """The old MOCK_ROUTE pointed at the wrong part of the country."""
        _login(client)
        points = client.get('/api/route?to=school').get_json()['waypoints']

        assert points[0] == pytest.approx(list(AYESHA_HOME), abs=1e-6)
        assert points[-1] == pytest.approx(list(BAHRIA_SCHOOL), abs=1e-6)

    def test_distance_matches_the_straight_line_when_interpolated(self, client):
        _login(client)
        data = client.get('/api/route?to=school').get_json()
        expected = distance_km(*AYESHA_HOME, *BAHRIA_SCHOOL)
        assert data['distance_km'] == pytest.approx(expected, abs=0.02)

    def test_duration_is_a_plausible_walk(self, client):
        _login(client)
        data = client.get('/api/route?to=school').get_json()
        # ~0.78 km at 4.5 km/h is about 10 minutes.
        assert 5 <= data['duration_min'] <= 20

    def test_destination_describes_the_school(self, client):
        """The UI uses this to label the pin, so it must be the real school."""
        _login(client)
        dest = client.get('/api/route?to=school').get_json()['destination']

        assert dest is not None
        assert dest['name'] == 'Beaconhouse Bahria Town'
        assert dest['source'] == 'registry'
        assert (dest['latitude'], dest['longitude']) == BAHRIA_SCHOOL
        assert dest['distance_km'] == pytest.approx(0.78, abs=0.1)

    def test_to_param_is_optional(self, client):
        # Omitting the end point means "my school" regardless of `to=`.
        _login(client)
        assert client.get('/api/route').get_json()['destination'] is not None

    def test_a_principal_gets_their_own_school(self, client):
        _login(client, PRINCIPAL)
        dest = client.get('/api/route?to=school').get_json()['destination']
        assert dest['name'] == 'Roots Millennium F-8'
        assert dest['distance_km'] == pytest.approx(0.0, abs=0.05)  # lives on campus


# ============================================================
# 3. EXPLICIT COORDINATES
# ============================================================
class TestRouteExplicitCoordinates:
    def test_uses_the_given_endpoints(self, client):
        _login(client)
        data = client.get('/api/route?start_lat=33.60&start_lon=73.10'
                          '&end_lat=33.65&end_lon=73.15').get_json()

        assert data['waypoints'][0] == pytest.approx([33.60, 73.10], abs=1e-6)
        assert data['waypoints'][-1] == pytest.approx([33.65, 73.15], abs=1e-6)
        # No school lookup happened, so there is nothing to describe.
        assert data['destination'] is None

    def test_explicit_end_with_home_as_start(self, client):
        _login(client)
        data = client.get('/api/route?end_lat=33.60&end_lon=73.10').get_json()
        assert data['waypoints'][0] == pytest.approx(list(AYESHA_HOME), abs=1e-6)
        assert data['waypoints'][-1] == pytest.approx([33.60, 73.10], abs=1e-6)

    @pytest.mark.parametrize('query', [
        'start_lat=91&start_lon=73.1&end_lat=33.6&end_lon=73.2',
        'start_lat=33.5&start_lon=181&end_lat=33.6&end_lon=73.2',
        'start_lat=33.5&start_lon=73.1&end_lat=-95&end_lon=73.2',
        'start_lat=33.5&start_lon=73.1&end_lat=33.6&end_lon=abc',
        'start_lat=abc&start_lon=73.1&end_lat=33.6&end_lon=73.2',
    ])
    def test_out_of_bounds_or_non_numeric_coordinates_are_rejected(self, client, query):
        _login(client)
        response = client.get(f'/api/route?{query}')
        assert response.status_code == 400
        assert 'error' in response.get_json()

    def test_half_a_start_pair_is_rejected(self, client):
        """A lat without a lon must be a 400, not a silent home fallback."""
        _login(client)
        response = client.get('/api/route?start_lat=33.6&end_lat=33.7&end_lon=73.2')
        assert response.status_code == 400

    def test_start_is_required_when_the_account_has_no_pin(self, client, monkeypatch):
        monkeypatch.setattr(app_module, 'get_current_user',
                            lambda: FakeUser(school_name='Beaconhouse Bahria Town'))
        _login(client)
        response = client.get('/api/route?end_lat=33.6&end_lon=73.2')
        assert response.status_code == 400
        assert 'start_lat' in response.get_json()['error']


# ============================================================
# 4. DEGRADATION — never break the map
# ============================================================
class TestRouteDegradation:
    def test_unplaceable_school_is_a_clean_404(self, client, monkeypatch):
        monkeypatch.setattr(app_module, 'get_current_user',
                            lambda: FakeUser(latitude=33.5, longitude=73.1,
                                             school_name='School That Does Not Exist'))
        _login(client)
        response = client.get('/api/route?to=school')
        assert response.status_code == 404
        assert 'School location is not available' in response.get_json()['error']

    def test_osrm_response_is_flipped_to_leaflet_order(self, monkeypatch):
        """OSRM geometry is [lon, lat]; Leaflet needs [lat, lon].

        Guarded at the unit level because the endpoint can never reach OSRM in
        tests — a silent un-flipped geometry would draw the route in the sea.
        """
        from modules import geo_services

        class FakeResponse:
            status_code = 200

            def json(self):
                return {'routes': [{
                    'distance': 900.0,
                    'duration': 700.0,
                    'geometry': {'coordinates': [[73.1543, 33.5348], [73.1600, 33.5400]]},
                }]}

        monkeypatch.setattr(geo_services.requests, 'get', lambda *a, **k: FakeResponse())
        route = geo_services.walking_route(*AYESHA_HOME, *BAHRIA_SCHOOL)

        assert route['source'] == 'osrm'
        assert route['waypoints'][0] == pytest.approx(list(AYESHA_HOME), abs=1e-6)
        assert route['distance_km'] == 0.9
        assert route['duration_min'] == 12

    def test_unreachable_osrm_still_returns_a_line(self):
        from modules import geo_services
        route = geo_services.walking_route(*AYESHA_HOME, *BAHRIA_SCHOOL)
        assert route['source'] == 'interpolated'
        assert len(route['waypoints']) == 10


# ============================================================
# 5. GEOCODE ENDPOINT
# ============================================================
class TestGeocodeEndpoint:
    def test_publicly_readable_and_empty_when_offline(self, client):
        # Registration uses this before login, so it must not require a session.
        response = client.get('/api/geocode?q=Bahria Town Phase 8')
        assert response.status_code == 200
        assert response.get_json() == {'results': []}

    @pytest.mark.parametrize('query', ['', 'ab', '   ', 'a'])
    def test_short_query_is_rejected(self, client, query):
        response = client.get(f'/api/geocode?q={query.strip()}')
        assert response.status_code == 400
        assert response.get_json()['results'] == []

    def test_missing_query_is_rejected(self, client):
        assert client.get('/api/geocode').status_code == 400

    def test_returns_nominatim_results_when_reachable(self, client, monkeypatch):
        monkeypatch.setattr(app_module, 'geocode', lambda q, limit=5: [
            {'label': 'Bahria Town Phase 8, Rawalpindi', 'latitude': 33.54, 'longitude': 73.16},
        ])
        results = client.get('/api/geocode?q=Bahria Town').get_json()['results']
        assert len(results) == 1
        assert results[0]['latitude'] == 33.54
