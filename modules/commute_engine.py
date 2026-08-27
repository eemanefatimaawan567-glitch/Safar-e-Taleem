import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2


PETROL_PRICE = 343.00  # fallback; live price passed as param
AVERAGE_MILEAGE = 15
SCHOOL_DAYS = 22

MAX_WALKING_GROUP_SIZE = 6
MAX_CARPOOL_SIZE = 4

# DBSCAN grouping radius (0.5 km)
GROUP_DISTANCE_KM = 0.5


def distance_km(lat1, lon1, lat2, lon2):

    R = 6371

    lat1 = radians(lat1)
    lon1 = radians(lon1)

    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return R * c


def calculate_fuel_cost(
    daily_distance_km,
    petrol_price=PETROL_PRICE
):

    monthly_distance = (
        daily_distance_km * SCHOOL_DAYS
    )

    fuel_used = (
        monthly_distance / AVERAGE_MILEAGE
    )

    return round(
        fuel_used * petrol_price,
        2
    )


def calculate_carpool_saving(
    students,
    daily_distance_km,
    petrol_price=PETROL_PRICE
):

    vehicles_before = students

    vehicles_after = int(
        np.ceil(
            students / MAX_CARPOOL_SIZE
        )
    )

    monthly_distance = (
        daily_distance_km * SCHOOL_DAYS
    )

    fuel_per_vehicle = (
        monthly_distance / AVERAGE_MILEAGE
    )

    individual_cost = (
        vehicles_before
        * fuel_per_vehicle
        * petrol_price
    )

    shared_cost = (
        vehicles_after
        * fuel_per_vehicle
        * petrol_price
    )

    saving = (
        individual_cost - shared_cost
    )

    return {
        "vehicles_before": vehicles_before,
        "vehicles_after": vehicles_after,
        "monthly_saving": round(saving, 2),
        "saving_per_student": round(
            saving / students, 2
        )
    }


def recommend_transport(
    school_distance,
    group_size
):

    if school_distance <= 1.0:

        return "Supervised Walking Group"

    elif school_distance <= 3.0:

        return "Shared Transport"

    elif group_size >= 2:

        return "Carpool"

    else:

        return "Individual Transport"


# ---------------------------------------------------------
# DBSCAN CLUSTERING — groups nearby families
# ---------------------------------------------------------

def cluster_families(users, eps_km=GROUP_DISTANCE_KM, min_samples=2):
    """
    Run DBSCAN clustering on a list of User objects with lat/lng.

    Args:
        users: list of User objects (must have .latitude, .longitude)
        eps_km: clustering radius in km (default 0.5 km)
        min_samples: minimum users to form a cluster

    Returns:
        list of dicts, each representing a transport group:
        [{
            'cluster_id': int,
            'members': [User, ...],
            'transport_type': str,
            'avg_distance_km': float,
            'school_name': str
        }]
    """
    from sklearn.cluster import DBSCAN as _DBSCAN

    # Filter users that have GPS coordinates
    geo_users = [u for u in users if u.latitude and u.longitude]

    if len(geo_users) < min_samples:
        # Not enough users to cluster — return single group if any
        if geo_users:
            return [{
                'cluster_id': 0,
                'members': geo_users,
                'transport_type': recommend_transport(2.5, len(geo_users)),
                'avg_distance_km': 2.5,
                'school_name': geo_users[0].school_name or 'Unknown School',
            }]
        return []

    # Convert to radians for haversine
    coords = np.radians(
        [[u.latitude, u.longitude] for u in geo_users]
    )

    eps_rad = eps_km / 6371.0  # Earth radius in km

    db = _DBSCAN(eps=eps_rad, min_samples=min_samples, metric='haversine')
    labels = db.fit_predict(coords)

    # Group users by cluster label
    clusters = {}
    noise_users = []

    for i, label in enumerate(labels):
        if label == -1:
            noise_users.append(geo_users[i])
        else:
            clusters.setdefault(label, []).append(geo_users[i])

    # Build result list
    results = []
    for cid, members in clusters.items():
        # Calculate average pairwise distance within cluster
        total_dist = 0
        count = 0
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                total_dist += distance_km(
                    members[i].latitude, members[i].longitude,
                    members[j].latitude, members[j].longitude
                )
                count += 1
        avg_dist = round(total_dist / count, 2) if count > 0 else 0

        school = members[0].school_name or 'Unknown School'
        transport = recommend_transport(avg_dist, len(members))

        results.append({
            'cluster_id': int(cid),
            'members': members,
            'transport_type': transport,
            'avg_distance_km': avg_dist,
            'school_name': school,
        })

    # Add noise users as solo groups
    for i, user in enumerate(noise_users):
        results.append({
            'cluster_id': -1,
            'members': [user],
            'transport_type': 'Individual Transport',
            'avg_distance_km': 0,
            'school_name': user.school_name or 'Unknown School',
        })

    return results


# ---------------------------------------------------------
# MOHALLAH STUDY PODS — device-owner / non-owner matching
# ---------------------------------------------------------

MAX_STUDY_POD_DISTANCE_KM = 1.0
MAX_STUDY_POD_SIZE = 3  # non-owners per device-owning host


def form_study_pods(families, max_distance_km=MAX_STUDY_POD_DISTANCE_KM, max_pod_size=MAX_STUDY_POD_SIZE):
    """
    Reuses the same proximity logic as the commute clustering, but matches on
    device access instead of walking distance: each family with a smartphone
    or laptop ("owner") hosts up to `max_pod_size` nearby families without one
    ("non-owners"), so kids can share a single screen for online/hybrid days.

    Args:
        families: list of User objects with .has_smart_device, .latitude, .longitude
        max_distance_km: how far a non-owner can be from their host and still be matched
        max_pod_size: max number of non-owner families per host

    Returns:
        (pods, unmatched) where:
          pods: list of dicts:
            {
                'owner': User,
                'members': [User, ...],       # non-owner families assigned to this host
                'distances_km': [float, ...], # matching order to members
                'avg_distance_km': float,
            }
          unmatched: list of User (non-owners with no eligible host nearby —
                     these are the families who need Offline Learning Packets instead)
    """
    owners = sorted(
        [f for f in families if f.has_smart_device and f.latitude and f.longitude],
        key=lambda u: u.id,
    )
    non_owners = [f for f in families if not f.has_smart_device and f.latitude and f.longitude]

    pods = []
    assigned_ids = set()

    for owner in owners:
        candidates = []
        for n in non_owners:
            if n.id in assigned_ids:
                continue
            d = distance_km(owner.latitude, owner.longitude, n.latitude, n.longitude)
            if d <= max_distance_km:
                candidates.append((d, n))

        candidates.sort(key=lambda x: x[0])
        chosen = candidates[:max_pod_size]

        if chosen:
            for _, n in chosen:
                assigned_ids.add(n.id)
            pods.append({
                'owner': owner,
                'members': [n for _, n in chosen],
                'distances_km': [round(d, 2) for d, _ in chosen],
                'avg_distance_km': round(sum(d for d, _ in chosen) / len(chosen), 2),
            })

    unmatched = [n for n in non_owners if n.id not in assigned_ids]
    return pods, unmatched