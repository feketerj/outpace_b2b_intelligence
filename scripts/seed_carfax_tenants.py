"""
Seed script for carfax tenants and users - v3 spec
Creates 6 tenants and 13 users (1 super admin + 2 per tenant)
"""
import os
from datetime import datetime, timezone, timedelta

import bcrypt
from pymongo import MongoClient


# Existing tenants (PRESERVE IDs)
TENANT_A_ID = "8aa521eb-56ad-4727-8f09-c01fc7921c21"
TENANT_B_ID = "e4e0b3b4-90ec-4c32-88d8-534aa563ed5d"

# New tenants per v3 spec
TENANT_EXPIRED_ID = "00000000-0000-0000-0000-000000000001"
TENANT_NOQUOTA_ID = "00000000-0000-0000-0000-000000000002"
TENANT_MASTER_ID = "00000000-0000-0000-0000-000000000003"
TENANT_NORAG_ID = "00000000-0000-0000-0000-000000000004"


def hash_pw(password: str) -> str:
    """Hash password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_db():
    """Get MongoDB connection using env vars with 127.0.0.1 default."""
    mongo_url = os.getenv("MONGO_URL", "mongodb://127.0.0.1:27017")
    db_name = os.getenv("DB_NAME", "outpace_intelligence")
    client = MongoClient(mongo_url)
    return client, client[db_name]


def create_tenant(
    tenant_id: str,
    slug: str,
    name: str,
    now: str,
    month_key: str,
    is_master_client: bool = False,
    chat_enabled: bool = True,
    rag_enabled: bool = True,
    monthly_message_limit: int = 100,
    subscription_end: str = None,
):
    """Create a tenant document with all required fields."""
    return {
        "id": tenant_id,
        "slug": slug,
        "name": name,
        "is_master_client": is_master_client,
        "chat_policy": {
            "enabled": chat_enabled,
            "monthly_message_limit": monthly_message_limit,
            "max_user_chars": 2000,
            "max_assistant_tokens": 1000,
            "max_turns_history": 10,
        },
        "rag_policy": {
            "enabled": rag_enabled,
            "max_documents": 100,
            "max_document_size_mb": 10,
        },
        "chat_usage": {"month": month_key, "messages_used": 0},
        "subscription_end": subscription_end,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }


def create_user(
    user_id: str,
    email: str,
    full_name: str,
    role: str,
    tenant_id: str,
    hashed_password: str,
    now: str,
):
    """Create a user document with all required fields."""
    return {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "tenant_id": tenant_id,
        "hashed_password": hashed_password,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }


def main():
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    month_key = now_iso[:7]
    yesterday = (now - timedelta(days=1)).isoformat()

    # Pre-compute password hashes once for efficiency
    test_password_hash = hash_pw(os.environ["CARFAX_TENANT_A_PASSWORD"])
    admin_password_hash = hash_pw(os.environ["CARFAX_ADMIN_PASSWORD"])

    # Define all 6 tenants per v3 spec
    tenants = [
        # Tenant A - chat+rag enabled (PRESERVE EXISTING)
        create_tenant(
            tenant_id=TENANT_A_ID,
            slug="tenant-a",
            name="Tenant A",
            now=now_iso,
            month_key=month_key,
            chat_enabled=True,
            rag_enabled=True,
        ),
        # Tenant B - separate silo (PRESERVE EXISTING)
        create_tenant(
            tenant_id=TENANT_B_ID,
            slug="tenant-b",
            name="Tenant B",
            now=now_iso,
            month_key=month_key,
            chat_enabled=True,
            rag_enabled=True,
        ),
        # Tenant Expired - subscription_end=yesterday
        create_tenant(
            tenant_id=TENANT_EXPIRED_ID,
            slug="tenant-expired",
            name="Tenant Expired",
            now=now_iso,
            month_key=month_key,
            subscription_end=yesterday,
        ),
        # Tenant NoQuota - monthly_message_limit=0
        create_tenant(
            tenant_id=TENANT_NOQUOTA_ID,
            slug="tenant-noquota",
            name="Tenant No Quota",
            now=now_iso,
            month_key=month_key,
            monthly_message_limit=0,
        ),
        # Tenant Master - is_master_client=true
        create_tenant(
            tenant_id=TENANT_MASTER_ID,
            slug="tenant-master",
            name="Tenant Master",
            now=now_iso,
            month_key=month_key,
            is_master_client=True,
        ),
        # Tenant NoRag - rag_policy.enabled=false
        create_tenant(
            tenant_id=TENANT_NORAG_ID,
            slug="tenant-norag",
            name="Tenant No RAG",
            now=now_iso,
            month_key=month_key,
            rag_enabled=False,
        ),
    ]

    # Define all 13 users (1 super admin + 2 per tenant: 1 admin + 1 regular user)
    users = [
        # Super admin (no tenant)
        create_user(
            user_id="super_admin_001",
            email=os.getenv("CARFAX_ADMIN_EMAIL", "admin@example.com"),
            full_name="Super Admin",
            role="super_admin",
            tenant_id=None,
            hashed_password=admin_password_hash,
            now=now_iso,
        ),
        # Tenant A users
        create_user(
            user_id=f"{TENANT_A_ID}-admin",
            email="admin@tenant-a.test",
            full_name="Tenant A Admin",
            role="tenant_admin",
            tenant_id=TENANT_A_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_A_ID}-user",
            email="user@tenant-a.test",
            full_name="Tenant A User",
            role="tenant_user",
            tenant_id=TENANT_A_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        # Tenant B users
        create_user(
            user_id=f"{TENANT_B_ID}-admin",
            email="admin@tenant-b.test",
            full_name="Tenant B Admin",
            role="tenant_admin",
            tenant_id=TENANT_B_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_B_ID}-user",
            email="user@tenant-b.test",
            full_name="Tenant B User",
            role="tenant_user",
            tenant_id=TENANT_B_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        # Tenant Expired users
        create_user(
            user_id=f"{TENANT_EXPIRED_ID}-admin",
            email="admin@tenant-expired.test",
            full_name="Tenant Expired Admin",
            role="tenant_admin",
            tenant_id=TENANT_EXPIRED_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_EXPIRED_ID}-user",
            email="user@tenant-expired.test",
            full_name="Tenant Expired User",
            role="tenant_user",
            tenant_id=TENANT_EXPIRED_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        # Tenant NoQuota users
        create_user(
            user_id=f"{TENANT_NOQUOTA_ID}-admin",
            email="admin@tenant-noquota.test",
            full_name="Tenant NoQuota Admin",
            role="tenant_admin",
            tenant_id=TENANT_NOQUOTA_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_NOQUOTA_ID}-user",
            email="user@tenant-noquota.test",
            full_name="Tenant NoQuota User",
            role="tenant_user",
            tenant_id=TENANT_NOQUOTA_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        # Tenant Master users
        create_user(
            user_id=f"{TENANT_MASTER_ID}-admin",
            email="admin@tenant-master.test",
            full_name="Tenant Master Admin",
            role="tenant_admin",
            tenant_id=TENANT_MASTER_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_MASTER_ID}-user",
            email="user@tenant-master.test",
            full_name="Tenant Master User",
            role="tenant_user",
            tenant_id=TENANT_MASTER_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        # Tenant NoRag users
        create_user(
            user_id=f"{TENANT_NORAG_ID}-admin",
            email="admin@tenant-norag.test",
            full_name="Tenant NoRag Admin",
            role="tenant_admin",
            tenant_id=TENANT_NORAG_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
        create_user(
            user_id=f"{TENANT_NORAG_ID}-user",
            email="user@tenant-norag.test",
            full_name="Tenant NoRag User",
            role="tenant_user",
            tenant_id=TENANT_NORAG_ID,
            hashed_password=test_password_hash,
            now=now_iso,
        ),
    ]

    client, db = get_db()

    # Upsert tenants (idempotent)
    for tenant in tenants:
        db.tenants.update_one(
            {"id": tenant["id"]},
            {"$set": tenant},
            upsert=True,
        )

    # Upsert users (idempotent)
    for user in users:
        db.users.update_one(
            {"id": user["id"]},
            {"$set": user},
            upsert=True,
        )

    tenant_count = db.tenants.count_documents({})
    user_count = db.users.count_documents({})

    print(f"Seeded {tenant_count} tenants:")
    for tenant in db.tenants.find({}, {"_id": 0, "id": 1, "slug": 1}):
        print(f"  - {tenant['slug']} ({tenant['id']})")

    print(f"\nSeeded {user_count} users:")
    for user in db.users.find({}, {"_id": 0, "id": 1, "email": 1, "role": 1}):
        print(f"  - {user['email']} ({user['role']})")

    client.close()

    print(f"\nTotal: tenants={tenant_count}, users={user_count}")


if __name__ == "__main__":
    main()
