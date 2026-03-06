#!/usr/bin/env python3
import os
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
from utils.auth import get_password_hash

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

async def create_super_admin():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Check if super admin already exists
    existing = await db.users.find_one({"role": "super_admin"})
    
    if existing:
        print("✓ Super admin already exists")
        print(f"  Email: {existing['email']}")
        return
    
    # Create super admin
    super_admin = {
        "id": str(uuid.uuid4()),
        "email": os.getenv("CARFAX_ADMIN_EMAIL", "admin@example.com"),
        "full_name": "Super Admin",
        "role": "super_admin",
        "tenant_id": None,
        "hashed_password": get_password_hash("outpace2025"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_login": None
    }
    
    await db.users.insert_one(super_admin)
    
    print("✓ Super admin created successfully!")
    print(f"  Email: {super_admin['email']}")
    print(f"  Password: outpace2025")
    print("\\n  ⚠️  Please change the password after first login!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_super_admin())
