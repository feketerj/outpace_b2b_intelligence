#!/usr/bin/env python3
"""
Client Onboarding Script

Creates a new tenant and tenant_admin user in a single idempotent command.
Skips creation if tenant (by slug) or user (by email) already exists.

Usage:
    python onboard_client.py --tenant-name "Acme Corp" --tenant-slug "acme-corp" \
        --admin-email "admin@acme.com" --admin-password "SecurePass123!"

Environment Variables:
    MONGO_URL: MongoDB connection string (default: mongodb://localhost:27017)
    DB_NAME: Database name (default: outpace_intelligence)
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from pymongo import MongoClient


def get_db():
    """Connect to MongoDB and return client and database."""
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "outpace_intelligence")
    client = MongoClient(mongo_url)
    return client, client[db_name]


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def extract_full_name(email: str) -> str:
    """Extract a full name from email address."""
    local_part = email.split("@")[0]
    # Replace common separators with spaces and title case
    name = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
    return name.title()


def create_tenant_document(tenant_id: str, name: str, slug: str, now: str) -> dict:
    """Create a tenant document with all required fields."""
    return {
        "id": tenant_id,
        "name": name,
        "slug": slug,
        "status": "active",
        "is_master_client": False,
        "created_at": now,
        "updated_at": now,
        "chat_policy": {
            "enabled": False,
            "monthly_message_limit": None,
            "max_user_chars": 2000,
            "max_assistant_tokens": 1000,
            "max_turns_history": 10,
        },
        "rag_policy": {
            "enabled": False,
            "max_documents": 0,
            "max_chunks": 0,
            "top_k": 5,
            "min_score": 0.25,
            "max_context_chars": 2000,
            "embed_model": "mistral-embed",
        },
    }


def create_user_document(
    user_id: str,
    email: str,
    hashed_password: str,
    full_name: str,
    tenant_id: str,
    now: str,
) -> dict:
    """Create a user document with all required fields."""
    return {
        "id": user_id,
        "email": email,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "role": "tenant_admin",
        "tenant_id": tenant_id,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }


def onboard_client(
    tenant_name: str,
    tenant_slug: str,
    admin_email: str,
    admin_password: str,
) -> dict:
    """
    Onboard a new client by creating tenant and admin user.

    Returns dict with status information about what was created or skipped.
    """
    client, db = get_db()
    result = {
        "tenant_created": False,
        "tenant_id": None,
        "tenant_status": None,
        "user_created": False,
        "user_id": None,
        "user_status": None,
    }

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Check if tenant already exists by slug
        existing_tenant = db.tenants.find_one({"slug": tenant_slug})
        if existing_tenant:
            result["tenant_id"] = existing_tenant["id"]
            result["tenant_status"] = "already exists"
            tenant_id = existing_tenant["id"]
        else:
            # Create new tenant
            tenant_id = str(uuid.uuid4())
            tenant_doc = create_tenant_document(tenant_id, tenant_name, tenant_slug, now)
            db.tenants.insert_one(tenant_doc)
            result["tenant_created"] = True
            result["tenant_id"] = tenant_id
            result["tenant_status"] = "created"

        # Check if user already exists by email
        existing_user = db.users.find_one({"email": admin_email})
        if existing_user:
            result["user_id"] = existing_user["id"]
            result["user_status"] = "already exists"
        else:
            # Create new admin user
            user_id = str(uuid.uuid4())
            hashed_password = hash_password(admin_password)
            full_name = extract_full_name(admin_email)
            user_doc = create_user_document(
                user_id, admin_email, hashed_password, full_name, tenant_id, now
            )
            db.users.insert_one(user_doc)
            result["user_created"] = True
            result["user_id"] = user_id
            result["user_status"] = "created"

        return result

    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Onboard a new client by creating tenant and admin user.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python onboard_client.py --tenant-name "Acme Corp" --tenant-slug "acme-corp" \\
        --admin-email "admin@acme.com" --admin-password "SecurePass123!"

Environment Variables:
    MONGO_URL   MongoDB connection string (default: mongodb://localhost:27017)
    DB_NAME     Database name (default: outpace_intelligence)
        """,
    )
    parser.add_argument(
        "--tenant-name",
        required=True,
        help="Display name for the tenant (e.g., 'Acme Corporation')",
    )
    parser.add_argument(
        "--tenant-slug",
        required=True,
        help="URL-safe slug for the tenant (e.g., 'acme-corp')",
    )
    parser.add_argument(
        "--admin-email",
        required=True,
        help="Email address for the tenant admin user",
    )
    parser.add_argument(
        "--admin-password",
        required=True,
        help="Password for the tenant admin user",
    )

    args = parser.parse_args()

    print(f"Onboarding client: {args.tenant_name} ({args.tenant_slug})")
    print(f"Admin user: {args.admin_email}")
    print()

    try:
        result = onboard_client(
            tenant_name=args.tenant_name,
            tenant_slug=args.tenant_slug,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
        )

        # Print tenant result
        if result["tenant_created"]:
            print(f"[CREATED] Tenant: {result['tenant_id']}")
        else:
            print(f"[SKIPPED] Tenant already exists: {result['tenant_id']}")

        # Print user result
        if result["user_created"]:
            print(f"[CREATED] User: {result['user_id']}")
        else:
            print(f"[SKIPPED] User already exists: {result['user_id']}")

        print()
        print("Onboarding complete.")

    except Exception as e:
        print(f"[ERROR] Onboarding failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
