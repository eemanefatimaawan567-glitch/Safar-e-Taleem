import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
import folium
from math import radians, sin, cos, sqrt, atan2


# ============================================================
# 1. SETTINGS
# ============================================================

# Prototype petrol price.
# Later we will replace this with a live/current price source.
PETROL_PRICE = 355

# Assumed average vehicle mileage
AVERAGE_MILEAGE = 15       # km per litre

# School days per month
SCHOOL_DAYS = 22

# DBSCAN grouping distance
GROUP_DISTANCE_KM = 0.5


# ============================================================
# 2. FICTIONAL AREAS + SCHOOLS
# ============================================================

AREAS = {
    "Bahria Town Phase 8": {
        "location": (33.5348, 73.1543),
        "school": "School A",
        "school_location": (33.5400, 73.1600),
    },

    "G-11 Islamabad": {
        "location": (33.6789, 72.9744),
        "school": "School B",
        "school_location": (33.6840, 72.9800),
    },

    "Satellite Town Rwp": {
        "location": (33.6255, 73.0426),
        "school": "School C",
        "school_location": (33.6300, 73.0500),
    },
}


# ============================================================
# 3. CREATE FICTIONAL STUDENT DATA
# ============================================================

STUDENTS_PER_AREA = 30

np.random.seed(42)

records = []
student_id = 1

first_names = [
    "Ali", "Ahmed", "Ayesha", "Zainab", "Hassan",
    "Sara", "Bilal", "Fatima", "Usman", "Hira",
    "Omar", "Mahnoor", "Faizan", "Amna", "Talha",
    "Iqra", "Hamza", "Noor", "Zain", "Laiba"
]


for area, info in AREAS.items():

    lat, lon = info["location"]
    school = info["school"]
    school_lat, school_lon = info["school_location"]

    for _ in range(STUDENTS_PER_AREA):

        # Create fictional nearby coordinates
        fake_lat = lat + np.random.uniform(-0.008, 0.008)
        fake_lon = lon + np.random.uniform(-0.008, 0.008)

        records.append({

            "student_id": student_id,

            "student_name": np.random.choice(first_names),

            "neighborhood": area,

            "latitude": round(fake_lat, 6),

            "longitude": round(fake_lon, 6),

            "grade": np.random.choice(
                [3, 4, 5, 6, 7, 8]
            ),

            "school": school,

            "school_latitude": school_lat,

            "school_longitude": school_lon,

        })

        student_id += 1


df = pd.DataFrame(records)


# ============================================================
# 4. DISTANCE CALCULATION
# ============================================================

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


# Calculate each student's distance to school

df["school_distance_km"] = df.apply(

    lambda row: distance_km(
        row["latitude"],
        row["longitude"],
        row["school_latitude"],
        row["school_longitude"]
    ),

    axis=1

)

df["school_distance_km"] = df[
    "school_distance_km"
].round(2)


# ============================================================
# 5. DBSCAN FAMILY/STUDENT CLUSTERING
# ============================================================

coords = np.radians(
    df[["latitude", "longitude"]].values
)

eps_rad = GROUP_DISTANCE_KM / 6371.0

db = DBSCAN(

    eps=eps_rad,

    min_samples=3,

    metric="haversine"

)

df["cluster"] = db.fit_predict(coords)


n_clusters = len(
    set(df["cluster"])
) - (
    1 if -1 in df["cluster"].values else 0
)

n_noise = (
    df["cluster"] == -1
).sum()


print("=" * 60)
print("SAFAR-E-TALEEM")
print("=" * 60)

print(
    f"Total students: {len(df)}"
)

print(
    f"Groups formed: {n_clusters}"
)

print(
    f"Students with no nearby match: {n_noise}"
)

print(
    f"Petrol price: Rs {PETROL_PRICE}/L"
)


# ============================================================
# 6. TRANSPORT RECOMMENDATION
# ============================================================

def recommend_transport(
    school_distance,
    group_size
):

    if school_distance <= 1:

        return "Supervised Walking Group"

    elif school_distance <= 3:

        return "Shared Transport"

    elif group_size >= 2:

        return "Carpool"

    else:

        return "Individual Transport"


# ============================================================
# 7. FUEL COST CALCULATOR
# ============================================================

def monthly_fuel_cost(
    daily_distance
):

    monthly_distance = (
        daily_distance
        * SCHOOL_DAYS
    )

    fuel_used = (
        monthly_distance
        / AVERAGE_MILEAGE
    )

    cost = (
        fuel_used
        * PETROL_PRICE
    )

    return round(cost, 2)


def carpool_savings(
    individual_cost,
    group_size
):

    if group_size <= 1:

        return 0

    shared_cost = (
        individual_cost
        / group_size
    )

    savings = (
        individual_cost
        - shared_cost
    )

    return round(savings, 2)


# ============================================================
# 8. REALISTIC GROUP PROCESSING
# ============================================================

MAX_WALKING_GROUP_SIZE = 6
MAX_CARPOOL_SIZE = 4


def calculate_carpool_savings(
    group_size,
    daily_distance_km
):
    """
    Compare individual vehicles with shared cars.

    Assumption:
    One car can carry up to 4 people.
    """

    # Individual vehicles
    individual_vehicles = group_size

    # Number of cars required for the group
    shared_vehicles = int(
        np.ceil(group_size / MAX_CARPOOL_SIZE)
    )

    # Monthly distance for one vehicle
    monthly_distance = (
        daily_distance_km * SCHOOL_DAYS
    )

    # Fuel required by one vehicle
    fuel_per_vehicle = (
        monthly_distance / AVERAGE_MILEAGE
    )

    # Cost if everyone uses separate vehicles
    individual_total_cost = (
        individual_vehicles
        * fuel_per_vehicle
        * PETROL_PRICE
    )

    # Cost if families share cars
    shared_total_cost = (
        shared_vehicles
        * fuel_per_vehicle
        * PETROL_PRICE
    )

    # Total group saving
    total_saving = (
        individual_total_cost
        - shared_total_cost
    )

    # Approximate saving per student
    saving_per_student = (
        total_saving / group_size
    )

    return {
        "individual_vehicles": individual_vehicles,
        "shared_vehicles": shared_vehicles,
        "individual_total_cost":
            round(individual_total_cost, 2),
        "shared_total_cost":
            round(shared_total_cost, 2),
        "total_saving":
            round(total_saving, 2),
        "saving_per_student":
            round(saving_per_student, 2)
    }


def split_into_groups(
    students,
    maximum_size
):
    """
    Split a large cluster into smaller
    practical transport groups.
    """

    groups = []

    for i in range(
        0,
        len(students),
        maximum_size
    ):

        groups.append(
            students[i:i + maximum_size]
        )

    return groups


# ============================================================
# 9. PROCESS DBSCAN CLUSTERS
# ============================================================

group_results = []

transport_group_id = 1


for cluster_id in sorted(
    df["cluster"].unique()
):

    # Ignore DBSCAN noise
    if cluster_id == -1:
        continue

    cluster_students = df[
        df["cluster"] == cluster_id
    ].copy()

    cluster_size = len(
        cluster_students
    )

    average_school_distance = round(
        cluster_students[
            "school_distance_km"
        ].mean(),
        2
    )

    school = cluster_students[
        "school"
    ].iloc[0]

    # --------------------------------------------------------
    # Decide transport type
    # --------------------------------------------------------

    if average_school_distance <= 1:

        transport_type = (
            "Supervised Walking Group"
        )

        maximum_group_size = (
            MAX_WALKING_GROUP_SIZE
        )

    elif average_school_distance <= 3:

        transport_type = (
            "Shared Transport"
        )

        maximum_group_size = (
            MAX_CARPOOL_SIZE
        )

    else:

        transport_type = "Carpool"

        maximum_group_size = (
            MAX_CARPOOL_SIZE
        )

    # --------------------------------------------------------
    # Split large DBSCAN cluster
    # --------------------------------------------------------

    student_groups = split_into_groups(
        cluster_students,
        maximum_group_size
    )

    for students_group in student_groups:

        group_size = len(
            students_group
        )

        daily_distance = (
            average_school_distance * 2
        )

        # ----------------------------------------------------
        # Walking group
        # ----------------------------------------------------

        if transport_type == (
            "Supervised Walking Group"
        ):

            result = {

                "transport_group":
                    transport_group_id,

                "dbscan_cluster":
                    cluster_id,

                "students":
                    group_size,

                "school":
                    school,

                "school_distance_km":
                    average_school_distance,

                "transport_type":
                    transport_type,

                "vehicles_before":
                    group_size,

                "vehicles_after":
                    0,

                "estimated_monthly_saving":
                    0,

                "saving_per_student":
                    0,

            }

        # ----------------------------------------------------
        # Carpool / shared transport
        # ----------------------------------------------------

        else:

            savings = calculate_carpool_savings(
                group_size,
                daily_distance
            )

            result = {

                "transport_group":
                    transport_group_id,

                "dbscan_cluster":
                    cluster_id,

                "students":
                    group_size,

                "school":
                    school,

                "school_distance_km":
                    average_school_distance,

                "transport_type":
                    transport_type,

                "vehicles_before":
                    savings[
                        "individual_vehicles"
                    ],

                "vehicles_after":
                    savings[
                        "shared_vehicles"
                    ],

                "estimated_monthly_saving":
                    savings[
                        "total_saving"
                    ],

                "saving_per_student":
                    savings[
                        "saving_per_student"
                    ],

            }

        group_results.append(result)

        transport_group_id += 1


# ============================================================
# 10. CREATE TRANSPORT GROUP DATAFRAME
# ============================================================

groups_df = pd.DataFrame(
    group_results
)


# ============================================================
# 11. PRINT SMART RECOMMENDATIONS
# ============================================================

print("\n")
print("=" * 60)
print("SMART COMMUTE RECOMMENDATIONS")
print("=" * 60)


for _, group in groups_df.iterrows():

    print(
        f"\nTRANSPORT GROUP "
        f"{int(group['transport_group'])}"
    )

    print(
        f"DBSCAN cluster: "
        f"{int(group['dbscan_cluster'])}"
    )

    print(
        f"Students: "
        f"{int(group['students'])}"
    )

    print(
        f"School: "
        f"{group['school']}"
    )

    print(
        f"School distance: "
        f"{group['school_distance_km']} km"
    )

    print(
        f"Recommendation: "
        f"{group['transport_type']}"
    )

    if group["transport_type"] != (
        "Supervised Walking Group"
    ):

        print(
            f"Vehicles before: "
            f"{int(group['vehicles_before'])}"
        )

        print(
            f"Vehicles after: "
            f"{int(group['vehicles_after'])}"
        )

        print(
            f"Estimated monthly group saving: "
            f"Rs {group['estimated_monthly_saving']}"
        )

        print(
            f"Estimated saving per student: "
            f"Rs {group['saving_per_student']}"
        )

    else:

        print(
            "Fuel cost: Rs 0 "
            "(walking recommendation)"
        )


# ============================================================
# 12. SAVE RESULTS
# ============================================================

df.to_csv(
    "fake_student_addresses.csv",
    index=False
)

groups_df.to_csv(
    "commute_groups.csv",
    index=False
)

print("\n")
print("=" * 60)
print("FILES SAVED")
print("=" * 60)

print("fake_student_addresses.csv")
print("commute_groups.csv")