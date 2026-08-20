import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2


PETROL_PRICE = 331.20  # fallback; live price passed as param
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

    return clusters