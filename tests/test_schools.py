"""
Safar-e-Taleem — Tests for the school registry & home->school commute
======================================================================
`recommend_transport()` expects the HOME -> SCHOOL distance. The dashboards
used to hand it the DBSCAN *cluster spread* (how far neighbours live from each
other), so a family 8 km from school who happened to have two neighbours nearby
was told to join a "Supervised Walking Group".

These tests pin the fix: the registry resolves schools, the commute maths is
honest about what it does not know, and — the regression that matters — a
far-from-school family clustered with close neighbours is no longer told to walk.

conftest sets SCHOOL_GEOCODING=0, so lookups stay on the offline registry and no
test can be perturbed by a slow or missing Nominatim reply. Tests that exercise
the geocoding path re-enable it explicitly and stub `geocode`.
"""
import pytest

import modules.schools as schools
from modules.commute_engine import (
    cluster_families,
    distance_km,
    recommend_transport,
)
from modules.schools import (
    DEFAULT_COMMUTE_KM,
    MAX_PLAUSIBLE_COMMUTE_KM,
    SCHOOLS,
    commute_distance_km,
    get_school_coords,
    home_to_school_km,
    school_info,
)


class FakeUser:
    """Stand-in for the SQLAlchemy User — only the fields schools.py reads."""

    def __init__(self, name='Test Parent', latitude=None, longitude=None,
                 school_name=None, neighborhood=None):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.school_name = school_name
        self.neighborhood = neighborhood


# Seeded demo family and its registered school (seed.py / modules.schools.py)
AYESHA_HOME = (33.5348, 73.1543)
BAHRIA_SCHOOL = (33.5400, 73.1600)


@pytest.fixture(autouse=True)
def _clear_resolution_cache():
    """`_resolved` memoises hits AND misses, so it must not leak between tests.

    Without this, a test that stubs `geocode` would poison the cache for every
    later test asking about the same unknown school.
    """
    schools._resolved.clear()
    yield
    schools._resolved.clear()


# ============================================================
# 1. COORDINATE RESOLUTION
# ============================================================
class TestGetSchoolCoords:
    def test_resolves_by_school_name(self):
        assert get_school_coords(school_name='Beaconhouse Bahria Town') == BAHRIA_SCHOOL

    def test_resolves_by_neighborhood_when_school_name_unknown(self):
        # Registration only guarantees one of the two fields.
        assert get_school_coords(school_name='Some Unregistered School',
                                 neighborhood='Bahria Town Phase 8') == BAHRIA_SCHOOL

    def test_resolution_ignores_case_and_padding(self):
        assert get_school_coords(school_name='  beaconhouse BAHRIA town ') == BAHRIA_SCHOOL

    def test_school_name_wins_over_neighborhood(self):
        # A family in Clifton whose child goes to the Bahria school must get the
        # Bahria pin — the school is where the commute actually ends.
        assert get_school_coords(school_name='Beaconhouse Bahria Town',
                                 neighborhood='Clifton Karachi') == BAHRIA_SCHOOL

    def test_loose_substring_match_handles_free_text(self):
        coords = get_school_coords(school_name='Beaconhouse Bahria Town Campus B')
        assert coords == BAHRIA_SCHOOL

    def test_unknown_school_returns_none_when_geocoding_disabled(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '0')
        assert get_school_coords(school_name='School That Does Not Exist') is None

    def test_no_arguments_returns_none(self):
        assert get_school_coords() is None
        assert get_school_coords(school_name='', neighborhood='') is None

    def test_every_registered_school_is_resolvable_both_ways(self):
        for area, school in SCHOOLS.items():
            expected = (school['lat'], school['lon'])
            assert get_school_coords(school_name=school['name']) == expected
            assert get_school_coords(neighborhood=area) == expected

    def test_registry_coordinates_are_valid_lat_lon(self):
        for area, school in SCHOOLS.items():
            assert -90 <= school['lat'] <= 90, area
            assert -180 <= school['lon'] <= 180, area


# ============================================================
# 2. GEOCODING FALLBACK + CACHING
# ============================================================
class TestGeocodingFallback:
    def test_falls_back_to_nominatim_for_unknown_school(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        calls = []

        def fake_geocode(query, limit=5):
            calls.append(query)
            return [{'latitude': 33.7, 'longitude': 73.0}]

        monkeypatch.setattr(schools, 'geocode', fake_geocode)
        assert get_school_coords(school_name='Real School Islamabad') == (33.7, 73.0)
        # The query must be country-scoped — geo_services only accepts Pakistan.
        assert calls == ['Real School Islamabad, Pakistan']

    def test_geocoding_kill_switch_prevents_the_call(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '0')

        def boom(*args, **kwargs):
            raise AssertionError('geocode must not run when SCHOOL_GEOCODING=0')

        monkeypatch.setattr(schools, 'geocode', boom)
        assert get_school_coords(school_name='Real School Islamabad') is None

    def test_negative_result_is_cached_so_a_miss_costs_one_lookup(self, monkeypatch):
        """A school we cannot place must not stall every dashboard render."""
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        calls = []
        monkeypatch.setattr(schools, 'geocode',
                            lambda q, limit=5: calls.append(q) or [])

        for _ in range(5):
            assert get_school_coords(school_name='Unplaceable School') is None
        assert len(calls) == 1

    def test_positive_result_is_cached(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        calls = []

        def fake_geocode(query, limit=5):
            calls.append(query)
            return [{'latitude': 31.5, 'longitude': 74.3}]

        monkeypatch.setattr(schools, 'geocode', fake_geocode)
        for _ in range(3):
            assert get_school_coords(school_name='Lahore School') == (31.5, 74.3)
        assert len(calls) == 1


# ============================================================
# 3. HOME -> SCHOOL DISTANCE
# ============================================================
class TestHomeToSchoolKm:
    def test_matches_haversine_to_registered_school(self):
        user = FakeUser(latitude=AYESHA_HOME[0], longitude=AYESHA_HOME[1],
                        school_name='Beaconhouse Bahria Town',
                        neighborhood='Bahria Town Phase 8')
        expected = distance_km(*AYESHA_HOME, *BAHRIA_SCHOOL)
        assert home_to_school_km(user) == pytest.approx(expected, abs=0.01)
        # Sanity band: catches a silently-wrong school pin.
        assert 0.5 < expected < 1.2

    def test_none_without_gps_coordinates(self):
        assert home_to_school_km(FakeUser(school_name='Beaconhouse Bahria Town')) is None

    def test_none_when_school_cannot_be_placed(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '0')
        user = FakeUser(latitude=33.5, longitude=73.1, school_name='Nowhere School')
        assert home_to_school_km(user) is None

    def test_none_for_user_that_is_none(self):
        assert home_to_school_km(None) is None

    def test_rejects_implausible_commute(self, monkeypatch):
        """A school on the other side of the country is a data-entry mistake.

        Feeding 1200 km into the fuel maths would produce an absurd cost, so the
        default is preferred over a number that looks measured but is not.
        """
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        monkeypatch.setattr(schools, 'geocode',
                            lambda q, limit=5: [{'latitude': 24.81, 'longitude': 67.035}])
        karachi_home = FakeUser(latitude=33.5348, longitude=73.1543,
                                school_name='Convent of Jesus & Mary')
        raw = distance_km(33.5348, 73.1543, 24.81, 67.035)
        assert raw > MAX_PLAUSIBLE_COMMUTE_KM
        assert home_to_school_km(karachi_home) is None

    def test_short_commute_is_not_discarded(self):
        # A school 200 m away is a real (walkable) answer, not a missing one.
        user = FakeUser(latitude=33.5390, longitude=73.1595,
                        school_name='Beaconhouse Bahria Town')
        km = home_to_school_km(user)
        assert km is not None and km < 0.2


class TestCommuteDistanceKm:
    def test_always_returns_a_number(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '0')
        assert commute_distance_km(None) == DEFAULT_COMMUTE_KM
        assert commute_distance_km(FakeUser()) == DEFAULT_COMMUTE_KM
        assert commute_distance_km(
            FakeUser(latitude=33.5, longitude=73.1, school_name='Unknown')
        ) == DEFAULT_COMMUTE_KM

    def test_measured_commute_beats_the_default(self):
        user = FakeUser(latitude=AYESHA_HOME[0], longitude=AYESHA_HOME[1],
                        school_name='Beaconhouse Bahria Town')
        km = commute_distance_km(user)
        assert km != DEFAULT_COMMUTE_KM
        assert 0.5 < km < 1.2

    def test_floors_a_zero_distance_to_keep_the_maths_sane(self):
        # Standing exactly on the school pin must not produce "0 km, 0 rupees".
        user = FakeUser(latitude=BAHRIA_SCHOOL[0], longitude=BAHRIA_SCHOOL[1],
                        school_name='Beaconhouse Bahria Town')
        assert home_to_school_km(user) == pytest.approx(0.0, abs=0.01)
        assert commute_distance_km(user) == 0.1


# ============================================================
# 4. SCHOOL INFO (dashboard / map payload)
# ============================================================
class TestSchoolInfo:
    def test_shape_and_registry_source(self):
        info = school_info(FakeUser(latitude=AYESHA_HOME[0], longitude=AYESHA_HOME[1],
                                    school_name='Beaconhouse Bahria Town',
                                    neighborhood='Bahria Town Phase 8'))
        assert info['name'] == 'Beaconhouse Bahria Town'
        assert (info['latitude'], info['longitude']) == BAHRIA_SCHOOL
        assert info['source'] == 'registry'
        assert info['distance_km'] == pytest.approx(0.78, abs=0.1)

    def test_geocoded_source_is_reported_honestly(self, monkeypatch):
        # The map labels the pin "(estimated path)" when it is not registered,
        # so `source` must distinguish the two.
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        monkeypatch.setattr(schools, 'geocode',
                            lambda q, limit=5: [{'latitude': 33.60, 'longitude': 73.10}])
        info = school_info(FakeUser(latitude=33.5348, longitude=73.1543,
                                    school_name='Unregistered Academy'))
        assert info['source'] == 'geocoded'
        assert info['distance_km'] is not None

    def test_none_when_unplaceable(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '0')
        assert school_info(FakeUser(latitude=33.5, longitude=73.1,
                                    school_name='Ghost School')) is None
        assert school_info(None) is None

    def test_distance_is_none_without_gps_but_pin_is_still_returned(self):
        info = school_info(FakeUser(school_name='Beaconhouse Bahria Town'))
        assert info['distance_km'] is None
        assert (info['latitude'], info['longitude']) == BAHRIA_SCHOOL

    def test_name_falls_back_to_neighborhood_then_generic(self, monkeypatch):
        monkeypatch.setenv('SCHOOL_GEOCODING', '1')
        monkeypatch.setattr(schools, 'geocode',
                            lambda q, limit=5: [{'latitude': 33.6, 'longitude': 73.0}])
        assert school_info(FakeUser(neighborhood='Bahria Town Phase 8',
                                    school_name=''))['name'] == 'School in Bahria Town Phase 8'


# ============================================================
# 5. THE REGRESSION — far from school, close to neighbours
# ============================================================
class TestCommuteDrivesRecommendation:
    """The whole point of the module: cluster spread must not decide the mode."""

    # Three homes within ~0.2 km of each other (so DBSCAN groups them) but
    # ~7.8 km from the registered Bahria school.
    FAR_FROM_SCHOOL = [
        ('Parent A', 33.6100, 73.1600),
        ('Parent B', 33.6105, 73.1605),
        ('Parent C', 33.6095, 73.1595),
    ]

    def _far_users(self):
        return [
            FakeUser(name=n, latitude=lat, longitude=lon,
                     school_name='Beaconhouse Bahria Town',
                     neighborhood='Bahria Town Phase 8')
            for n, lat, lon in self.FAR_FROM_SCHOOL
        ]

    def test_cluster_spread_alone_looks_walkable(self):
        # Confirms the premise of the old bug: neighbours are ~0.1 km apart.
        clusters = cluster_families(self._far_users())
        assert len(clusters) == 1
        assert clusters[0]['avg_distance_km'] <= 1.0
        assert clusters[0]['avg_school_distance_km'] is None

    def test_without_school_distance_the_group_is_told_to_walk(self):
        # The pre-fix behaviour, asserted so the contrast below is meaningful.
        clusters = cluster_families(self._far_users())
        assert clusters[0]['transport_type'] == 'Supervised Walking Group'

    def test_with_school_distance_the_group_gets_a_carpool(self):
        users = self._far_users()
        clusters = cluster_families(users, school_distance_fn=commute_distance_km)
        cluster = clusters[0]

        assert cluster['avg_school_distance_km'] > 7.0
        assert cluster['transport_type'] == 'Carpool'
        assert cluster['transport_type'] != 'Supervised Walking Group'

    def test_school_distance_fn_receives_each_member(self):
        seen = []

        def spy(user):
            seen.append(user.name)
            return 5.0

        cluster_families(self._far_users(), school_distance_fn=spy)
        assert sorted(seen) == ['Parent A', 'Parent B', 'Parent C']

    def test_a_failing_resolver_does_not_break_the_cluster(self):
        def explodes(user):
            raise RuntimeError('resolver blew up')

        clusters = cluster_families(self._far_users(), school_distance_fn=explodes)
        # Degrades to the old cluster-spread behaviour instead of raising.
        assert len(clusters) == 1
        assert clusters[0]['avg_school_distance_km'] is None

    def test_a_partially_failing_resolver_uses_the_members_it_can_place(self):
        users = self._far_users()

        def only_first(user):
            return 8.0 if user.name == 'Parent A' else None

        clusters = cluster_families(users, school_distance_fn=only_first)
        assert clusters[0]['avg_school_distance_km'] == 8.0

    def test_walkable_commute_still_recommends_walking(self):
        # The fix must not over-correct: a genuinely close family still walks.
        users = [
            FakeUser(name='Ayesha', latitude=33.5348, longitude=73.1543,
                     school_name='Beaconhouse Bahria Town',
                     neighborhood='Bahria Town Phase 8'),
            FakeUser(name='Hassan', latitude=33.5360, longitude=73.1555,
                     school_name='Beaconhouse Bahria Town',
                     neighborhood='Bahria Town Phase 8'),
        ]
        clusters = cluster_families(users, school_distance_fn=commute_distance_km)
        assert clusters[0]['transport_type'] == 'Supervised Walking Group'
        assert clusters[0]['avg_school_distance_km'] < 1.0

    def test_recommendation_thresholds_are_unchanged(self):
        # Guard the contract the registry feeds into.
        assert recommend_transport(0.8, 3) == 'Supervised Walking Group'
        assert recommend_transport(2.5, 3) == 'Shared Transport'
        assert recommend_transport(7.8, 3) == 'Carpool'
        assert recommend_transport(7.8, 1) == 'Individual Transport'


# ============================================================
# 6. SINGLE SOURCE OF TRUTH WITH THE SEEDER
# ============================================================
class TestSeedSharesRegistry:
    def test_seed_imports_the_same_registry(self):
        """seed.py must not keep a second copy that can drift out of sync."""
        import seed
        assert seed.SCHOOLS is SCHOOLS
