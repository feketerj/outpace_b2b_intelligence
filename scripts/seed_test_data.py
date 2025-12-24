#!/usr/bin/env python3
"""
seed_test_data.py - Comprehensive test data seeding per test-plan-v2.md Section 3.2

Seeds canonical test data for carfax.sh integration testing:
- 6 tenants (including edge cases: expired, no-quota, disabled, no-rag)
- 12 users (across all roles and tenants)
- 12 opportunities (CRUD, boundary, isolation, relationships)
- 6 intelligence records
- 11 test documents

Usage:
    python scripts/seed_test_data.py [--reset] [--verbose]

Options:
    --reset     Delete all existing test data before seeding
    --verbose   Print detailed output

Environment:
    MONGO_URL   MongoDB connection string (default: mongodb://localhost:27017)
    DB_NAME     Database name (default: outpace_intelligence)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from pymongo import MongoClient

# =============================================================================
# CANONICAL IDs (per test-plan-v2.md Section 3.2)
# =============================================================================

# Tenant IDs
TENANT_A_ID = "8aa521eb-56ad-4727-8f09-c01fc7921c21"
TENANT_B_ID = "e4e0b3b4-90ec-4c32-88d8-534aa563ed5d"
TENANT_EXPIRED_ID = "00000000-0000-0000-0000-000000000001"
TENANT_NOQUOTA_ID = "00000000-0000-0000-0000-000000000002"
TENANT_DISABLED_ID = "00000000-0000-0000-0000-000000000003"
TENANT_NORAG_ID = "00000000-0000-0000-0000-000000000004"

# User IDs
USER_IDS = {
    "USR-001": "super_admin_001",
    "USR-002": "tenant_a_admin_001",
    "USR-003": "tenant_b_admin_001",
    "USR-004": "tenant_a_user_001",
    "USR-005": "tenant_b_user_001",
    "USR-006": "tenant_a_inactive_001",
    "USR-007": "tenant_expired_user_001",
    "USR-008": "tenant_noquota_user_001",
    "USR-009": "tenant_a_user_002",
    "USR-010": "tenant_disabled_admin_001",
    "USR-011": "tenant_norag_user_001",
    "USR-012": "tenant_a_readonly_001",
}

# Opportunity IDs
OPP_IDS = {
    "OPP-001": "opp_clean_001",
    "OPP-002": "opp_minimal_001",
    "OPP-003": "opp_maxfields_001",
    "OPP-004": "opp_tenant_b_001",
    "OPP-005": "opp_expired_001",
    "OPP-006": "opp_future_001",
    "OPP-007": "opp_unicode_001",
    "OPP-008": "opp_large_desc_001",
    "OPP-009": "opp_with_intel_001",
    "OPP-010": "opp_with_docs_001",
    "OPP-011": "opp_synced_001",
    "OPP-012": "opp_archived_001",
}

# Intelligence IDs
INT_IDS = {
    "INT-001": "intel_001",
    "INT-002": "intel_002",
    "INT-003": "intel_003",
    "INT-004": "intel_004",
    "INT-005": "intel_005",
    "INT-006": "intel_006",
}


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_db():
    """Get MongoDB client and database."""
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "outpace_intelligence")
    client = MongoClient(mongo_url)
    return client, client[db_name]


def create_tenants(now: str, yesterday: str, month_key: str) -> list:
    """Create 6 canonical tenants per Section 3.2.1."""
    base_chat_policy = {
        "enabled": True,
        "monthly_message_limit": 100,
        "max_user_chars": 2000,
        "max_assistant_tokens": 1000,
        "max_turns_history": 10,
    }

    return [
        # Tenant A - Primary test tenant, all features enabled
        {
            "id": TENANT_A_ID,
            "slug": "tenant-a",
            "name": "Tenant A",
            "is_master_client": False,
            "chat_policy": base_chat_policy.copy(),
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": True,
            "subscription_end": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        # Tenant B - Cross-tenant isolation testing
        {
            "id": TENANT_B_ID,
            "slug": "tenant-b",
            "name": "Tenant B",
            "is_master_client": False,
            "chat_policy": base_chat_policy.copy(),
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": True,
            "subscription_end": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        # Expired Tenant - Subscription tests
        {
            "id": TENANT_EXPIRED_ID,
            "slug": "tenant-expired",
            "name": "Expired Tenant",
            "is_master_client": False,
            "chat_policy": base_chat_policy.copy(),
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": True,
            "subscription_end": yesterday,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        # No Quota Tenant - Quota exhaustion testing
        {
            "id": TENANT_NOQUOTA_ID,
            "slug": "tenant-noquota",
            "name": "No Quota Tenant",
            "is_master_client": False,
            "chat_policy": {
                "enabled": True,
                "monthly_message_limit": 0,
                "max_user_chars": 2000,
                "max_assistant_tokens": 1000,
                "max_turns_history": 10,
            },
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": True,
            "subscription_end": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        # Disabled Tenant - Feature toggle tests
        {
            "id": TENANT_DISABLED_ID,
            "slug": "tenant-disabled",
            "name": "Disabled Tenant",
            "is_master_client": False,
            "chat_policy": {
                "enabled": False,
                "monthly_message_limit": 0,
                "max_user_chars": 0,
                "max_assistant_tokens": 0,
                "max_turns_history": 0,
            },
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": False,
            "subscription_end": None,
            "status": "disabled",
            "created_at": now,
            "updated_at": now,
        },
        # No RAG Tenant - RAG disabled tests
        {
            "id": TENANT_NORAG_ID,
            "slug": "tenant-norag",
            "name": "No RAG Tenant",
            "is_master_client": False,
            "chat_policy": base_chat_policy.copy(),
            "chat_usage": {"month": month_key, "messages_used": 0},
            "rag_enabled": False,
            "subscription_end": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    ]


def create_users(now: str) -> list:
    """Create 12 canonical users per Section 3.2.2."""
    password_hash = hash_password("Test123!")
    admin_hash = hash_password("Admin123!")

    return [
        # USR-001: Super admin
        {
            "id": USER_IDS["USR-001"],
            "email": "admin@outpace.ai",
            "full_name": "Super Admin",
            "role": "super_admin",
            "tenant_id": None,
            "hashed_password": admin_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-002: Tenant A admin
        {
            "id": USER_IDS["USR-002"],
            "email": "admin-a@test.com",
            "full_name": "Tenant A Admin",
            "role": "tenant_admin",
            "tenant_id": TENANT_A_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-003: Tenant B admin
        {
            "id": USER_IDS["USR-003"],
            "email": "admin-b@test.com",
            "full_name": "Tenant B Admin",
            "role": "tenant_admin",
            "tenant_id": TENANT_B_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-004: Tenant A regular user
        {
            "id": USER_IDS["USR-004"],
            "email": "user-a@test.com",
            "full_name": "Tenant A User",
            "role": "tenant_user",
            "tenant_id": TENANT_A_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-005: Tenant B regular user
        {
            "id": USER_IDS["USR-005"],
            "email": "user-b@test.com",
            "full_name": "Tenant B User",
            "role": "tenant_user",
            "tenant_id": TENANT_B_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-006: Inactive user
        {
            "id": USER_IDS["USR-006"],
            "email": "inactive@test.com",
            "full_name": "Inactive User",
            "role": "tenant_user",
            "tenant_id": TENANT_A_ID,
            "hashed_password": password_hash,
            "is_active": False,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-007: Expired tenant user
        {
            "id": USER_IDS["USR-007"],
            "email": "expired@test.com",
            "full_name": "Expired Tenant User",
            "role": "tenant_user",
            "tenant_id": TENANT_EXPIRED_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-008: No quota user
        {
            "id": USER_IDS["USR-008"],
            "email": "noquota@test.com",
            "full_name": "No Quota User",
            "role": "tenant_user",
            "tenant_id": TENANT_NOQUOTA_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-009: Second tenant A user (concurrency testing)
        {
            "id": USER_IDS["USR-009"],
            "email": "user2-a@test.com",
            "full_name": "Tenant A User 2",
            "role": "tenant_user",
            "tenant_id": TENANT_A_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-010: Disabled tenant admin
        {
            "id": USER_IDS["USR-010"],
            "email": "admin-disabled@test.com",
            "full_name": "Disabled Tenant Admin",
            "role": "tenant_admin",
            "tenant_id": TENANT_DISABLED_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-011: No RAG user
        {
            "id": USER_IDS["USR-011"],
            "email": "norag@test.com",
            "full_name": "No RAG User",
            "role": "tenant_user",
            "tenant_id": TENANT_NORAG_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
        # USR-012: Read-only user
        {
            "id": USER_IDS["USR-012"],
            "email": "readonly@test.com",
            "full_name": "Read Only User",
            "role": "tenant_user",
            "tenant_id": TENANT_A_ID,
            "hashed_password": password_hash,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
        },
    ]


def create_opportunities(now: str, yesterday: str, future_30: str) -> list:
    """Create 12 canonical opportunities per Section 3.2.3."""
    large_description = "L" * 50000  # 50KB description

    return [
        # OPP-001: Clean opportunity - happy path CRUD
        {
            "id": OPP_IDS["OPP-001"],
            "title": "Clean Opportunity",
            "description": "A clean test opportunity for happy path testing.",
            "agency": "Test Agency",
            "estimated_value": 100000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-002: Minimal fields - empty handling
        {
            "id": OPP_IDS["OPP-002"],
            "title": "Minimal Fields",
            "tenant_id": TENANT_A_ID,
            "status": "active",
            "source": "manual",
            "created_at": now,
            "updated_at": now,
        },
        # OPP-003: Max fields - boundary testing
        {
            "id": OPP_IDS["OPP-003"],
            "title": "Max Fields Opportunity",
            "description": "Opportunity with all optional fields populated.",
            "agency": "Department of Defense",
            "estimated_value": 999999999.99,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "naics_code": "541512",
            "set_aside": "Small Business",
            "place_of_performance": "Washington, DC",
            "point_of_contact": "John Doe",
            "contact_email": "john.doe@test.gov",
            "solicitation_number": "SOL-2024-001",
            "posted_date": now,
            "response_deadline": future_30,
            "award_date": None,
            "contract_type": "Firm Fixed Price",
            "competition_type": "Full and Open",
            "created_at": now,
            "updated_at": now,
        },
        # OPP-004: Tenant B opportunity - isolation testing
        {
            "id": OPP_IDS["OPP-004"],
            "title": "Tenant B Opp",
            "description": "This opportunity belongs to Tenant B only.",
            "agency": "Tenant B Agency",
            "estimated_value": 50000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_B_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-005: Expired opportunity - date boundary
        {
            "id": OPP_IDS["OPP-005"],
            "title": "Expired Opp",
            "description": "Opportunity with due date in the past.",
            "agency": "Past Agency",
            "estimated_value": 25000.0,
            "due_date": yesterday,
            "status": "expired",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-006: Future opportunity - date boundary
        {
            "id": OPP_IDS["OPP-006"],
            "title": "Future Opp",
            "description": "Opportunity with due date 30 days in the future.",
            "agency": "Future Agency",
            "estimated_value": 75000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-007: Unicode opportunity - encoding testing
        {
            "id": OPP_IDS["OPP-007"],
            "title": "Unicode Opp: \u4e2d\u6587 \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4",
            "description": "Testing unicode: \u00e9\u00e8\u00ea \u00fc\u00f6\u00e4 \u00f1 \u2603 \u2764 \U0001f600",
            "agency": "International Agency \u00ae",
            "estimated_value": 100000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-008: Large description - size boundary
        {
            "id": OPP_IDS["OPP-008"],
            "title": "Large Description",
            "description": large_description,
            "agency": "Large Agency",
            "estimated_value": 200000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-009: With intelligence - relationship testing
        {
            "id": OPP_IDS["OPP-009"],
            "title": "With Intelligence",
            "description": "Opportunity that has linked intelligence records.",
            "agency": "Intelligence Agency",
            "estimated_value": 150000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "has_intelligence": True,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-010: With documents - upload relation testing
        {
            "id": OPP_IDS["OPP-010"],
            "title": "With Documents",
            "description": "Opportunity that has uploaded files.",
            "agency": "Document Agency",
            "estimated_value": 125000.0,
            "due_date": future_30,
            "status": "active",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "has_documents": True,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-011: Synced opportunity - sync testing
        {
            "id": OPP_IDS["OPP-011"],
            "title": "Synced Opp",
            "description": "Opportunity synced from HigherGov.",
            "agency": "Synced Agency",
            "estimated_value": 300000.0,
            "due_date": future_30,
            "status": "active",
            "source": "highergov",
            "external_id": "HG-2024-001",
            "tenant_id": TENANT_A_ID,
            "last_synced_at": now,
            "created_at": now,
            "updated_at": now,
        },
        # OPP-012: Archived opportunity - status testing
        {
            "id": OPP_IDS["OPP-012"],
            "title": "Archived Opp",
            "description": "Opportunity that has been archived.",
            "agency": "Archive Agency",
            "estimated_value": 50000.0,
            "due_date": yesterday,
            "status": "archived",
            "source": "manual",
            "tenant_id": TENANT_A_ID,
            "archived_at": now,
            "created_at": now,
            "updated_at": now,
        },
    ]


def create_intelligence(now: str) -> list:
    """Create 6 canonical intelligence records per Section 3.2.4."""
    return [
        # INT-001: Happy path intelligence for OPP-009
        {
            "id": INT_IDS["INT-001"],
            "opportunity_id": OPP_IDS["OPP-009"],
            "tenant_id": TENANT_A_ID,
            "content": "Competitive landscape analysis for opportunity.",
            "source": "analyst",
            "category": "competitive",
            "created_at": now,
            "updated_at": now,
        },
        # INT-002: CRUD testing for OPP-001
        {
            "id": INT_IDS["INT-002"],
            "opportunity_id": OPP_IDS["OPP-001"],
            "tenant_id": TENANT_A_ID,
            "content": "Market research data for clean opportunity.",
            "source": "research",
            "category": "market",
            "created_at": now,
            "updated_at": now,
        },
        # INT-003: Isolation testing for Tenant B (OPP-004)
        {
            "id": INT_IDS["INT-003"],
            "opportunity_id": OPP_IDS["OPP-004"],
            "tenant_id": TENANT_B_ID,
            "content": "Tenant B specific intelligence data.",
            "source": "analyst",
            "category": "strategic",
            "created_at": now,
            "updated_at": now,
        },
        # INT-004: Update testing for OPP-001
        {
            "id": INT_IDS["INT-004"],
            "opportunity_id": OPP_IDS["OPP-001"],
            "tenant_id": TENANT_A_ID,
            "content": "Intelligence record for update testing.",
            "source": "system",
            "category": "technical",
            "created_at": now,
            "updated_at": now,
        },
        # INT-005: Delete testing for OPP-001
        {
            "id": INT_IDS["INT-005"],
            "opportunity_id": OPP_IDS["OPP-001"],
            "tenant_id": TENANT_A_ID,
            "content": "Intelligence record for delete testing.",
            "source": "manual",
            "category": "notes",
            "created_at": now,
            "updated_at": now,
        },
        # INT-006: Unicode content for OPP-007
        {
            "id": INT_IDS["INT-006"],
            "opportunity_id": OPP_IDS["OPP-007"],
            "tenant_id": TENANT_A_ID,
            "content": "Unicode intelligence: \u4e2d\u6587 \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4 \u00e9\u00e8\u00ea \U0001f600",
            "source": "international",
            "category": "global",
            "created_at": now,
            "updated_at": now,
        },
    ]


def create_test_documents(project_root: Path) -> None:
    """Create 11 test documents per Section 3.2.5."""
    test_files_dir = project_root / "test_files"
    test_files_dir.mkdir(exist_ok=True)

    # test_clean.csv - Normal upload (5KB)
    clean_rows = ["title,agency,due_date,estimated_value"]
    for i in range(100):
        clean_rows.append(f"Opportunity {i},Agency {i},2025-12-31,{i * 1000}")
    (test_files_dir / "test_clean.csv").write_text("\n".join(clean_rows))

    # test_large.csv - Size boundary (2MB)
    large_rows = ["title,agency,due_date,estimated_value,description"]
    desc = "D" * 1000
    for i in range(2000):
        large_rows.append(f"Large Opp {i},Agency {i},2025-12-31,{i * 1000},{desc}")
    (test_files_dir / "test_large.csv").write_text("\n".join(large_rows))

    # test_unicode.csv - UTF-8 encoding (10KB)
    unicode_rows = ["title,agency,due_date,estimated_value"]
    unicode_rows.append("\u4e2d\u6587\u673a\u4f1a,\u56fd\u9632\u90e8,2025-12-31,100000")
    unicode_rows.append("\u65e5\u672c\u6a5f\u4f1a,\u9632\u885b\u7701,2025-12-31,200000")
    unicode_rows.append("\ud55c\uad6d \uae30\ud68c,\uad6d\ubc29\ubd80,2025-12-31,300000")
    unicode_rows.append("Caf\u00e9 Contract,Minist\u00e8re,2025-12-31,50000")
    unicode_rows.append("Stra\u00dfe Project,Ministerium,2025-12-31,75000")
    for i in range(200):
        unicode_rows.append(f"Unicode {i} \u2603,Agency \u2764 {i},2025-12-31,{i * 500}")
    (test_files_dir / "test_unicode.csv").write_text("\n".join(unicode_rows), encoding="utf-8")

    # test_malformed.csv - Parse errors (1KB)
    malformed_content = """title,agency,due_date,estimated_value
"Unclosed quote,Agency A,2025-12-31,100000
Normal Row,Agency B,2025-12-31,200000
Too,Many,Fields,Here,Extra,More
Missing Fields
,,,
"Has ""quotes"" inside",Agency C,2025-12-31,300000"""
    (test_files_dir / "test_malformed.csv").write_text(malformed_content)

    # test_empty.csv - Empty handling (0B)
    (test_files_dir / "test_empty.csv").write_text("")

    # test_headers_only.csv - No data rows (100B)
    (test_files_dir / "test_headers_only.csv").write_text(
        "title,agency,due_date,estimated_value,description,naics_code"
    )

    # test_10k_rows.csv - Performance (1MB)
    perf_rows = ["title,agency,due_date,estimated_value"]
    for i in range(10000):
        perf_rows.append(f"Performance Test {i},Perf Agency {i % 100},2025-12-31,{i * 100}")
    (test_files_dir / "test_10k_rows.csv").write_text("\n".join(perf_rows))

    # test_logo.png - Logo upload (create minimal valid PNG, ~50KB simulated)
    # Minimal 1x1 PNG
    png_header = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # 8-bit RGB
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0x00, 0x00, 0x00,  # compressed data
        0x01, 0x00, 0x01, 0xE5, 0x27, 0xDE, 0xFC, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    # Pad to ~50KB
    padding = b'\x00' * (50 * 1024 - len(png_header))
    (test_files_dir / "test_logo.png").write_bytes(png_header + padding)

    # test_logo_large.png - Size limit (5MB)
    large_padding = b'\x00' * (5 * 1024 * 1024 - len(png_header))
    (test_files_dir / "test_logo_large.png").write_bytes(png_header + large_padding)

    # test_rag_doc.txt - RAG indexing (10KB)
    rag_content = """Government Contracting Best Practices

This document covers best practices for government contracting including:

1. Proposal Writing
   - Executive Summary
   - Technical Approach
   - Management Plan
   - Past Performance

2. Compliance Requirements
   - FAR Clauses
   - DFARS Requirements
   - Small Business Goals

3. Contract Types
   - Firm Fixed Price (FFP)
   - Cost Plus Fixed Fee (CPFF)
   - Time and Materials (T&M)

""" + ("Lorem ipsum dolor sit amet. " * 200)
    (test_files_dir / "test_rag_doc.txt").write_text(rag_content)

    # test_rag_large.txt - Chunking test (100KB)
    large_rag = """Large Document for RAG Chunking Tests

""" + ("This is a paragraph for testing RAG document chunking. " * 100 + "\n\n") * 50
    (test_files_dir / "test_rag_large.txt").write_text(large_rag)


def seed_database(db, reset: bool, verbose: bool) -> dict:
    """Seed all test data into database."""
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    yesterday = (now_dt - timedelta(days=1)).isoformat()
    future_30 = (now_dt + timedelta(days=30)).isoformat()
    month_key = now[:7]

    stats = {
        "tenants": 0,
        "users": 0,
        "opportunities": 0,
        "intelligence": 0,
    }

    # Optionally reset collections
    if reset:
        if verbose:
            print("Resetting collections...")
        db.tenants.delete_many({})
        db.users.delete_many({})
        db.opportunities.delete_many({})
        db.intelligence.delete_many({})

    # Seed tenants
    tenants = create_tenants(now, yesterday, month_key)
    for tenant in tenants:
        db.tenants.update_one(
            {"id": tenant["id"]},
            {"$set": tenant},
            upsert=True
        )
        stats["tenants"] += 1
        if verbose:
            print(f"  Upserted tenant: {tenant['slug']}")

    # Seed users
    users = create_users(now)
    for user in users:
        db.users.update_one(
            {"id": user["id"]},
            {"$set": user},
            upsert=True
        )
        stats["users"] += 1
        if verbose:
            print(f"  Upserted user: {user['email']}")

    # Seed opportunities
    opportunities = create_opportunities(now, yesterday, future_30)
    for opp in opportunities:
        db.opportunities.update_one(
            {"id": opp["id"]},
            {"$set": opp},
            upsert=True
        )
        stats["opportunities"] += 1
        if verbose:
            print(f"  Upserted opportunity: {opp['title'][:30]}...")

    # Seed intelligence
    intelligence = create_intelligence(now)
    for intel in intelligence:
        db.intelligence.update_one(
            {"id": intel["id"]},
            {"$set": intel},
            upsert=True
        )
        stats["intelligence"] += 1
        if verbose:
            print(f"  Upserted intelligence: {intel['id']}")

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed canonical test data per test-plan-v2.md Section 3.2"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing test data before seeding"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output"
    )
    parser.add_argument(
        "--skip-files",
        action="store_true",
        help="Skip creating test document files"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Seeding Test Data (test-plan-v2.md Section 3.2)")
    print("=" * 60)

    # Get database connection
    client, db = get_db()
    print(f"Database: {db.name}")
    print(f"Reset mode: {args.reset}")
    print()

    # Seed database
    stats = seed_database(db, args.reset, args.verbose)

    print()
    print("Database seeding complete:")
    print(f"  Tenants:       {stats['tenants']}")
    print(f"  Users:         {stats['users']}")
    print(f"  Opportunities: {stats['opportunities']}")
    print(f"  Intelligence:  {stats['intelligence']}")

    # Create test files
    if not args.skip_files:
        print()
        print("Creating test document files...")
        project_root = Path(__file__).parent.parent
        create_test_documents(project_root)
        print(f"  Test files created in: {project_root / 'test_files'}")

    client.close()
    print()
    print("=" * 60)
    print("Seeding complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
