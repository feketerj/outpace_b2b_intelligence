#!/usr/bin/env python3
"""
Initialize super admin user for OutPace Intelligence platform.
Run this once to create the default super admin account.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import uuid
from dotenv import load_dotenv
from pathlib import Path
from utils.auth import get_password_hash, validate_password_policy

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

async def create_super_admin():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    admin_email = os.environ.get("SUPER_ADMIN_EMAIL") or os.environ.get("CARFAX_ADMIN_EMAIL")
    admin_password = os.environ.get("SUPER_ADMIN_PASSWORD") or os.environ.get("CARFAX_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        raise RuntimeError(
            "Set SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD "
            "(or CARFAX_ADMIN_EMAIL and CARFAX_ADMIN_PASSWORD) before running this script."
        )

    password_ok, password_errors = validate_password_policy(admin_password)
    if not password_ok:
        raise RuntimeError("SUPER_ADMIN_PASSWORD does not meet policy: " + "; ".join(password_errors))
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    try:
        # Check if super admin already exists
        existing = await db.users.find_one({"role": "super_admin"})

        if existing:
            print("Super admin already exists")
            print(f"  Email: {existing['email']}")
            return

        # Create super admin
        super_admin = {
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "full_name": "Super Admin",
            "role": "super_admin",
            "tenant_id": None,
            "hashed_password": get_password_hash(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }

        await db.users.insert_one(super_admin)

        print("Super admin created successfully")
        print(f"  Email: {super_admin['email']}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(create_super_admin())
