"""
Safar-e-Taleem — Unit Tests for the Commute Engine
====================================================
Covers: Haversine distance, fuel cost, carpool savings,
transport recommendation, DBSCAN clustering, and study pod matching.

Run with:  pytest tests/ -v
"""
import sys
import os
import math
import pytest
from types import SimpleNamespace

# Ensure the project root is on sys.path so modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.commute_engine import (
    distance_km,
    calculate_fuel_cost,
    calculate_carpool_saving,
    recommend_transport,
    cluster_families,
    form_study_pods,
    SCHOOL_DAYS,
    AVERAGE_MILEAGE,
)


# ============================================================
# 1. HAVERSINE DISTANCE
# ============================================================
class TestDistanceKm:
    """Validate the Haversine distance calculation."""

    def test_same_point_returns_zero(self):
        assert distance_km(33.6844, 73.0479, 33.6844, 73.0479) == 0.0

    def test_known_distance_islamabad_to_lahore(self):
        # Islamabad (33.6844, 73.0479) → Lahore (31.5204, 74.3587)
        # Actual great-circle ≈ 270 km (road distance is ~380 km)
        d = distance_km(33.6844, 73.0479, 31.5204, 74.3587)
        assert 260 < d < 280, f"Expected ~270 km, got {d:.1f}"

    def test_short_distance_within_city(self):
        # Two points ~1 km apart in Islamabad
        d = distance_km(33.6844, 73.0479, 33.6934, 73.0479)
        assert 0.9 < d < 1.1, f"Expected ~1 km, got {d:.2f}"

    def test_symmetry(self):
        """d(A, B) must equal d(B, A)."""
        d1 = distance_km(33.6844, 73.0479, 31.5204, 74.3587)
        d2 = distance_km(31.5204, 74.3587, 33.6844, 73.0479)
        assert abs(d1 - d2) < 0.001

    def test_antipodal_points(self):
        """Maximum possible distance on Earth ≈ 20,015 km."""
        d = distance_km(0, 0, 0, 180)
        assert 20000 < d < 20100


# ============================================================
# 2. FUEL COST CALCULATION
# ============================================================
class TestCalculateFuelCost:
    """Validate monthly fuel cost computation."""

    def test_basic_calculation(self):
        # 5 km/day × 22 school days = 110 km/month
        # 110 / 15 km/L = 7.33 L × Rs 343 = Rs 2,515.56
        cost = calculate_fuel_cost(5.0, 343.0)
        expected = round((5.0 * SCHOOL_DAYS / AVERAGE_MILEAGE) * 343.0, 2)
        assert cost == expected

    def test_zero_distance_returns_zero(self):
        assert calculate_fuel_cost(0.0, 343.0) == 0.0

    def test_higher_petrol_price_increases_cost(self):
        cost_low = calculate_fuel_cost(5.0, 300.0)
        cost_high = calculate_fuel_cost(5.0, 400.0)
        assert cost_high > cost_low

    def test_returns_float_rounded_to_2dp(self):
        cost = calculate_fuel_cost(7.3, 343.0)
        assert isinstance(cost, float)
        # Check it has at most 2 decimal places
        assert cost == round(cost, 2)


# ============================================================
# 3. CARPOOL SAVINGS
# ============================================================
class TestCalculateCarpoolSaving:
    """Validate carpool economics model."""

    def test_single_student_no_saving(self):
        """1 student can't carpool alone — 0 savings."""
        result = calculate_carpool_saving(1, 5.0, 343.0)
        assert result['monthly_saving'] == 0.0
        assert result['vehicles_before'] == 1
        assert result['vehicles_after'] == 1

    def test_four_students_one_car(self):
        """4 students fit in 1 car → 75% cost reduction."""
        result = calculate_carpool_saving(4, 5.0, 343.0)
        assert result['vehicles_before'] == 4
        assert result['vehicles_after'] == 1
        assert result['monthly_saving'] > 0
        # Per-student saving should be total / 4
        assert abs(result['saving_per_student'] - result['monthly_saving'] / 4) < 0.01

    def test_five_students_need_two_cars(self):
        """5 students → ceil(5/4) = 2 vehicles."""
        result = calculate_carpool_saving(5, 5.0, 343.0)
        assert result['vehicles_after'] == 2

    def test_savings_increase_with_more_students(self):
        s3 = calculate_carpool_saving(3, 5.0, 343.0)['monthly_saving']
        s8 = calculate_carpool_saving(8, 5.0, 343.0)['monthly_saving']
        assert s8 > s3

    def test_result_structure(self):
        result = calculate_carpool_saving(4, 5.0, 343.0)
        assert 'vehicles_before' in result
        assert 'vehicles_after' in result
        assert 'monthly_saving' in result
        assert 'saving_per_student' in result


# ============================================================
# 4. TRANSPORT RECOMMENDATION
# ============================================================
class TestRecommendTransport:
    """Validate the rule-based transport recommender."""

    def test_walking_group_for_short_distance(self):
        assert recommend_transport(0.5, 3) == "Supervised Walking Group"
        assert recommend_transport(1.0, 5) == "Supervised Walking Group"

    def test_shared_transport_for_medium_distance(self):
        assert recommend_transport(1.5, 2) == "Shared Transport"
        assert recommend_transport(3.0, 4) == "Shared Transport"

    def test_carpool_for_far_with_group(self):
        assert recommend_transport(5.0, 3) == "Carpool"

    def test_individual_for_far_alone(self):
        assert recommend_transport(5.0, 1) == "Individual Transport"

    def test_boundary_values(self):
        # Exactly 1.0 km → walking
        assert recommend_transport(1.0, 2) == "Supervised Walking Group"
        # Exactly 3.0 km with group ≥ 2 → shared
        assert recommend_transport(3.0, 2) == "Shared Transport"


# ============================================================
# 5. DBSCAN CLUSTERING
# ============================================================
class TestClusterFamilies:
    """Validate DBSCAN-based family clustering."""

    def _make_user(self, id, lat, lon, school='Test School'):
        return SimpleNamespace(id=id, latitude=lat, longitude=lon, school_name=school)

    def test_empty_list_returns_empty(self):
        assert cluster_families([]) == []

    def test_single_user_returns_one_group(self):
        """1 user with min_samples=2 → returned as solo group."""
        users = [self._make_user(1, 33.6844, 73.0479)]
        result = cluster_families(users, min_samples=2)
        assert len(result) == 1
        assert len(result[0]['members']) == 1

    def test_nearby_users_cluster_together(self):
        """Two users 200m apart should cluster at eps=0.5km."""
        users = [
            self._make_user(1, 33.6844, 73.0479),
            self._make_user(2, 33.6860, 73.0479),  # ~180m away
        ]
        result = cluster_families(users, eps_km=0.5, min_samples=2)
        # Should form 1 cluster with 2 members
        clustered = [r for r in result if r['cluster_id'] >= 0]
        assert len(clustered) == 1
        assert len(clustered[0]['members']) == 2

    def test_far_users_stay_separate(self):
        """Users 50 km apart should NOT cluster at eps=0.5km."""
        users = [
            self._make_user(1, 33.6844, 73.0479),   # Islamabad
            self._make_user(2, 31.5204, 74.3587),    # Lahore
        ]
        result = cluster_families(users, eps_km=0.5, min_samples=2)
        # Both should be noise (solo groups with cluster_id = -1)
        solo = [r for r in result if r['cluster_id'] == -1]
        assert len(solo) == 2

    def test_users_without_gps_are_skipped(self):
        """Users with no lat/lng should not appear in results."""
        users = [
            self._make_user(1, None, None),
            self._make_user(2, 33.6844, 73.0479),
        ]
        result = cluster_families(users, min_samples=1)
        all_members = [m for r in result for m in r['members']]
        assert len(all_members) == 1
        assert all_members[0].id == 2

    def test_result_structure(self):
        users = [
            self._make_user(1, 33.6844, 73.0479),
            self._make_user(2, 33.6860, 73.0479),
        ]
        result = cluster_families(users, eps_km=0.5, min_samples=2)
        for group in result:
            assert 'cluster_id' in group
            assert 'members' in group
            assert 'transport_type' in group
            assert 'avg_distance_km' in group
            assert 'school_name' in group


# ============================================================
# 6. STUDY POD MATCHING
# ============================================================
class TestFormStudyPods:
    """Validate device-owner / non-owner study pod matching."""

    def _make_family(self, id, lat, lon, has_device=True):
        return SimpleNamespace(
            id=id, latitude=lat, longitude=lon,
            has_smart_device=has_device, school_name='Test School',
        )

    def test_no_families_returns_empty(self):
        pods, unmatched = form_study_pods([])
        assert pods == []
        assert unmatched == []

    def test_all_owners_no_pods(self):
        """No non-owners → no pods needed, no unmatched."""
        families = [
            self._make_family(1, 33.6844, 73.0479, True),
            self._make_family(2, 33.6860, 73.0479, True),
        ]
        pods, unmatched = form_study_pods(families)
        assert pods == []
        assert unmatched == []

    def test_non_owner_near_host_gets_matched(self):
        """1 owner + 1 non-owner within 1 km → 1 pod."""
        families = [
            self._make_family(1, 33.6844, 73.0479, True),   # owner
            self._make_family(2, 33.6860, 73.0479, False),  # non-owner ~180m away
        ]
        pods, unmatched = form_study_pods(families)
        assert len(pods) == 1
        assert pods[0]['owner'].id == 1
        assert len(pods[0]['members']) == 1
        assert pods[0]['members'][0].id == 2
        assert unmatched == []

    def test_non_owner_too_far_is_unmatched(self):
        """Non-owner 50 km from nearest host → unmatched."""
        families = [
            self._make_family(1, 33.6844, 73.0479, True),   # Islamabad
            self._make_family(2, 31.5204, 74.3587, False),  # Lahore
        ]
        pods, unmatched = form_study_pods(families)
        assert pods == []
        assert len(unmatched) == 1
        assert unmatched[0].id == 2

    def test_max_pod_size_respected(self):
        """Host takes at most max_pod_size non-owners."""
        owner = self._make_family(0, 33.6844, 73.0479, True)
        non_owners = [
            self._make_family(i, 33.6844 + 0.001 * i, 73.0479, False)
            for i in range(1, 6)  # 5 non-owners, all nearby
        ]
        pods, unmatched = form_study_pods([owner] + non_owners, max_pod_size=3)
        assert len(pods) == 1
        assert len(pods[0]['members']) == 3
        assert len(unmatched) == 2

    def test_distances_km_populated(self):
        """Each matched member should have a distance entry."""
        families = [
            self._make_family(1, 33.6844, 73.0479, True),
            self._make_family(2, 33.6860, 73.0479, False),
            self._make_family(3, 33.6880, 73.0479, False),
        ]
        pods, unmatched = form_study_pods(families)
        assert len(pods) == 1
        assert len(pods[0]['distances_km']) == len(pods[0]['members'])
        for d in pods[0]['distances_km']:
            assert d >= 0

    def test_no_double_assignment(self):
        """A non-owner should be assigned to at most one host."""
        families = [
            self._make_family(1, 33.6844, 73.0479, True),   # host A
            self._make_family(2, 33.6846, 73.0479, True),   # host B (~22m from A)
            self._make_family(3, 33.6845, 73.0479, False),  # non-owner between both
        ]
        pods, unmatched = form_study_pods(families)
        # Non-owner should appear in exactly one pod
        total_assigned = sum(len(p['members']) for p in pods)
        assert total_assigned == 1
        assert unmatched == []
