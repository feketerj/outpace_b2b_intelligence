import os
from datetime import datetime, timezone

import bcrypt
from pymongo import MongoClient


TENANT_A_ID = "8aa521eb-56ad-4727-8f09-c01fc7921c21"
TENANT_B_ID = "e4e0b3b4-90ec-4c32-88d8-534aa563ed5d"


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_db():
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "outpace_intelligence")
    client = MongoClient(mongo_url)
    return client, client[db_name]


def main():
    now = datetime.now(timezone.utc).isoformat()
    users = [
        {
            "id": "super_admin_001",
            "email": os.environ.get("CARFAX_ADMIN_EMAIL", "admin@example.com"),
            "full_name": "Super Admin",
            "role": "super_admin",
            "tenant_id": None,
            "hashed_password": hash_pw(os.environ.get("CARFAX_ADMIN_PASSWORD", "changeme")),
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        {
            "id": "tenant_a_user_001",
            "email": "tenant-b-test@test.com",
            "full_name": "Tenant A User",
            "role": "tenant_user",
            "tenant_id": TENANT_A_ID,
            "hashed_password": hash_pw(os.environ.get("CARFAX_TENANT_A_PASSWORD", "changeme")),
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        {
            "id": "tenant_b_user_001",
            "email": "enchandia-test@test.com",
            "full_name": "Tenant B User",
            "role": "tenant_user",
            "tenant_id": TENANT_B_ID,
            "hashed_password": hash_pw(os.environ.get("CARFAX_TENANT_A_PASSWORD", "changeme")),
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
    ]

    client, db = get_db()
    db.users.delete_many({})
    db.users.insert_many(users)

    print(f"Created {db.users.count_documents({})} users in {db.name}")
    client.close()


if __name__ == "__main__":
    main()
