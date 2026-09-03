"""
Safar-e-Taleem — Seed Script
Populates the database with 10 demo families (real GPS coordinates)
so the hackathon demo shows a fully populated dashboard immediately.

Usage:
    python seed.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash

# ─────────────────────────────────────────────
# SCHOOL COORDINATES (fictional schools in each area)
# ─────────────────────────────────────────────
# The canonical registry lives in modules/schools.py so the exact same
# coordinates drive both the demo seed and the runtime home -> school distance
# maths. Importing it here keeps the two from drifting apart.
from modules.schools import SCHOOLS  # noqa: E402


# ─────────────────────────────────────────────
# DEMO FAMILIES (with real area GPS coords)
# ─────────────────────────────────────────────
DEMO_USERS = [
    # Bahria Town Phase 8 — 3 families close together
    {
        "name": "Ayesha Khan",
        "email": "ayesha@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234501-1",
        "phone": "03001234501",
        "neighborhood": "Bahria Town Phase 8",
        "address": "House 12, Block C, Bahria Town Phase 8",
        "latitude": 33.5348,
        "longitude": 73.1543,
        "children_count": 2,
        "school_name": "Beaconhouse Bahria Town",
        "has_smart_device": True,
    },
    {
        "name": "Hassan Ali",
        "email": "hassan@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234502-1",
        "phone": "03001234502",
        "neighborhood": "Bahria Town Phase 8",
        "address": "House 45, Block C, Bahria Town Phase 8",
        "latitude": 33.5360,
        "longitude": 73.1555,
        "children_count": 1,
        "school_name": "Beaconhouse Bahria Town",
        "has_smart_device": False,
    },
    {
        "name": "Sana Ahmed",
        "email": "sana@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234503-1",
        "phone": "03001234503",
        "neighborhood": "Bahria Town Phase 8",
        "address": "House 8, Block D, Bahria Town Phase 8",
        "latitude": 33.5328,
        "longitude": 73.1530,
        "children_count": 3,
        "school_name": "Beaconhouse Bahria Town",
        "has_smart_device": False,
    },

    # G-11 Islamabad — 2 families
    {
        "name": "Usman Malik",
        "email": "usman@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234504-1",
        "phone": "03001234504",
        "neighborhood": "G-11 Islamabad",
        "address": "Flat 3, Street 9, G-11/2",
        "latitude": 33.6789,
        "longitude": 72.9744,
        "children_count": 2,
        "school_name": "City School G-11",
        "has_smart_device": True,
    },
    {
        "name": "Fatima Bibi",
        "email": "fatima@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234505-1",
        "phone": "03001234505",
        "neighborhood": "G-11 Islamabad",
        "address": "House 22, Street 5, G-11/1",
        "latitude": 33.6800,
        "longitude": 72.9760,
        "children_count": 1,
        "school_name": "City School G-11",
        "has_smart_device": False,
    },

    # F-8 Islamabad — 2 families
    {
        "name": "Bilal Raza",
        "email": "bilal@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234506-1",
        "phone": "03001234506",
        "neighborhood": "F-8 Islamabad",
        "address": "House 7, Street 12, F-8/1",
        "latitude": 33.7100,
        "longitude": 73.0400,
        "children_count": 2,
        "school_name": "Roots Millennium F-8",
        "has_smart_device": False,
    },
    {
        "name": "Hira Noor",
        "email": "hira@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234507-1",
        "phone": "03001234507",
        "neighborhood": "F-8 Islamabad",
        "address": "Flat 5, F-8 Markaz",
        "latitude": 33.7115,
        "longitude": 73.0420,
        "children_count": 1,
        "school_name": "Roots Millennium F-8",
        "has_smart_device": True,
    },

    # Satellite Town Rwp — 1 family
    {
        "name": "Maryam Shah",
        "email": "maryam@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234508-1",
        "phone": "03001234508",
        "neighborhood": "Satellite Town Rwp",
        "address": "House 15, Block A, Satellite Town",
        "latitude": 33.6255,
        "longitude": 73.0426,
        "children_count": 2,
        "school_name": "Allied School Satellite Town",
        "has_smart_device": False,
    },

    # DHA Phase 2 — 1 family
    {
        "name": "Ahmed Hassan",
        "email": "ahmed@demo.com",
        "password": "demo123",
        "role": "parent",
        "cnic": "37405-1234509-1",
        "phone": "03001234509",
        "neighborhood": "DHA Phase 2",
        "address": "House 88, Phase 2, DHA",
        "latitude": 33.6100,
        "longitude": 73.0900,
        "children_count": 3,
        "school_name": "LGS DHA Phase 2",
        "has_smart_device": True,
    },

    # School Principal — 1
    {
        "name": "Dr. Zainab Qureshi",
        "email": "principal@demo.com",
        "password": "demo123",
        "role": "principal",
        "cnic": "37405-1234510-1",
        "phone": "03001234510",
        "neighborhood": "F-8 Islamabad",
        "address": "School Campus, F-8 Markaz",
        "latitude": 33.7140,
        "longitude": 73.0450,
        "children_count": 0,
        "school_name": "Roots Millennium F-8",
    },
]


def seed():
    from app import app, db, User, PetrolPrice
    with app.app_context():
        # Check if already seeded
        existing = User.query.filter_by(email="ayesha@demo.com").first()
        if existing:
            print("⚠️  Database already seeded. Skipping.")
            print("   To re-seed, delete instance/database.db first.")
            return

        # Create tables
        db.create_all()

        # Seed demo users
        for u in DEMO_USERS:
            new_user = User(
                name=u["name"],
                email=u["email"],
                password=generate_password_hash(u["password"]),
                role=u["role"],
                cnic=u["cnic"],
                phone=u.get("phone", ""),
                is_verified=True,
                address=u["address"],
                neighborhood=u["neighborhood"],
                latitude=u["latitude"],
                longitude=u["longitude"],
                children_count=u["children_count"],
                school_name=u["school_name"],
                has_smart_device=u.get("has_smart_device", True),
            )
            db.session.add(new_user)

        # Seed initial petrol price
        if PetrolPrice.query.count() == 0:
            db.session.add(PetrolPrice(price=343.00, source="seed"))

        db.session.commit()

        parent_count = User.query.filter_by(role="parent").count()
        principal_count = User.query.filter_by(role="principal").count()
        print("=" * 50)
        print("  SAFAR-E-TALEEM — DATABASE SEEDED")
        print("=" * 50)
        print(f"  Parents:    {parent_count}")
        print(f"  Principals: {principal_count}")
        print(f"  Password:   demo123 (for all users)")
        print()
        print("  Demo login emails:")
        for u in DEMO_USERS:
            print(f"    {u['email']:25s} ({u['role']})")
        print("=" * 50)


if __name__ == "__main__":
    seed()
