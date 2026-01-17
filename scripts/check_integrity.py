#!/usr/bin/env python3
"""
Referential Integrity Checker

Scans the database for orphaned records and dangling references.
Run this before deployments or as a scheduled maintenance task.

Usage:
    python scripts/check_integrity.py
    python scripts/check_integrity.py --fix  # Auto-fix orphaned records

Exit codes:
    0 - No integrity issues
    1 - Integrity issues found
    2 - Error during check
"""

import asyncio
import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrityChecker:
    """Check and optionally fix referential integrity issues."""

    def __init__(self, db, fix_mode: bool = False):
        self.db = db
        self.fix_mode = fix_mode
        self.issues = []
        self.fixes = []

    async def run_all_checks(self) -> dict:
        """Run all integrity checks."""
        logger.info("Starting integrity check...")
        start_time = datetime.now(timezone.utc)

        # Get all valid tenant IDs
        valid_tenant_ids = set()
        async for tenant in self.db.tenants.find({}, {"id": 1}):
            valid_tenant_ids.add(tenant["id"])
        logger.info(f"Found {len(valid_tenant_ids)} valid tenants")

        # Run checks
        await self.check_orphaned_opportunities(valid_tenant_ids)
        await self.check_orphaned_users(valid_tenant_ids)
        await self.check_orphaned_chat_turns(valid_tenant_ids)
        await self.check_orphaned_knowledge_snippets(valid_tenant_ids)
        await self.check_orphaned_kb_chunks()
        await self.check_duplicate_external_ids()

        # Calculate duration
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "status": "clean" if not self.issues else "issues_found",
            "issues_count": len(self.issues),
            "fixes_count": len(self.fixes),
            "issues": self.issues,
            "fixes": self.fixes,
            "duration_seconds": round(duration, 2),
            "timestamp": start_time.isoformat()
        }

    async def check_orphaned_opportunities(self, valid_tenant_ids: set):
        """Find opportunities without valid tenant."""
        logger.info("Checking for orphaned opportunities...")

        orphans = []
        async for opp in self.db.opportunities.find(
            {"tenant_id": {"$nin": list(valid_tenant_ids)}},
            {"id": 1, "tenant_id": 1, "title": 1}
        ):
            orphans.append({
                "id": opp["id"],
                "tenant_id": opp.get("tenant_id"),
                "title": opp.get("title", "")[:50]
            })

        if orphans:
            self.issues.append({
                "type": "ORPHANED_OPPORTUNITIES",
                "count": len(orphans),
                "sample": orphans[:5]
            })
            logger.warning(f"[INTEGRITY] Found {len(orphans)} orphaned opportunities")

            if self.fix_mode:
                result = await self.db.opportunities.delete_many(
                    {"tenant_id": {"$nin": list(valid_tenant_ids)}}
                )
                self.fixes.append({
                    "type": "DELETED_ORPHANED_OPPORTUNITIES",
                    "count": result.deleted_count
                })
                logger.info(f"[FIX] Deleted {result.deleted_count} orphaned opportunities")

    async def check_orphaned_users(self, valid_tenant_ids: set):
        """Find users without valid tenant (except super admins)."""
        logger.info("Checking for orphaned users...")

        orphans = []
        async for user in self.db.users.find(
            {
                "tenant_id": {"$nin": list(valid_tenant_ids), "$ne": None},
                "role": {"$ne": "super_admin"}
            },
            {"id": 1, "tenant_id": 1, "email": 1}
        ):
            orphans.append({
                "id": user["id"],
                "tenant_id": user.get("tenant_id"),
                "email": user.get("email", "")
            })

        if orphans:
            self.issues.append({
                "type": "ORPHANED_USERS",
                "count": len(orphans),
                "sample": orphans[:5]
            })
            logger.warning(f"[INTEGRITY] Found {len(orphans)} orphaned users")

            if self.fix_mode:
                # Don't auto-delete users - too dangerous
                logger.info("[FIX] Skipping user deletion (manual review required)")

    async def check_orphaned_chat_turns(self, valid_tenant_ids: set):
        """Find chat turns without valid tenant."""
        logger.info("Checking for orphaned chat turns...")

        count = await self.db.chat_turns.count_documents(
            {"tenant_id": {"$nin": list(valid_tenant_ids)}}
        )

        if count > 0:
            self.issues.append({
                "type": "ORPHANED_CHAT_TURNS",
                "count": count
            })
            logger.warning(f"[INTEGRITY] Found {count} orphaned chat turns")

            if self.fix_mode:
                result = await self.db.chat_turns.delete_many(
                    {"tenant_id": {"$nin": list(valid_tenant_ids)}}
                )
                self.fixes.append({
                    "type": "DELETED_ORPHANED_CHAT_TURNS",
                    "count": result.deleted_count
                })
                logger.info(f"[FIX] Deleted {result.deleted_count} orphaned chat turns")

    async def check_orphaned_knowledge_snippets(self, valid_tenant_ids: set):
        """Find knowledge snippets without valid tenant."""
        logger.info("Checking for orphaned knowledge snippets...")

        count = await self.db.knowledge_snippets.count_documents(
            {"tenant_id": {"$nin": list(valid_tenant_ids)}}
        )

        if count > 0:
            self.issues.append({
                "type": "ORPHANED_KNOWLEDGE_SNIPPETS",
                "count": count
            })
            logger.warning(f"[INTEGRITY] Found {count} orphaned knowledge snippets")

            if self.fix_mode:
                result = await self.db.knowledge_snippets.delete_many(
                    {"tenant_id": {"$nin": list(valid_tenant_ids)}}
                )
                self.fixes.append({
                    "type": "DELETED_ORPHANED_KNOWLEDGE_SNIPPETS",
                    "count": result.deleted_count
                })

    async def check_orphaned_kb_chunks(self):
        """Find KB chunks without valid document."""
        logger.info("Checking for orphaned KB chunks...")

        # Get all valid document IDs
        valid_doc_ids = set()
        async for doc in self.db.kb_documents.find({}, {"id": 1}):
            valid_doc_ids.add(doc["id"])

        if not valid_doc_ids:
            # No documents means no chunks should exist
            count = await self.db.kb_chunks.count_documents({})
            if count > 0:
                self.issues.append({
                    "type": "ORPHANED_KB_CHUNKS",
                    "count": count,
                    "note": "No KB documents exist but chunks found"
                })
            return

        count = await self.db.kb_chunks.count_documents(
            {"document_id": {"$nin": list(valid_doc_ids)}}
        )

        if count > 0:
            self.issues.append({
                "type": "ORPHANED_KB_CHUNKS",
                "count": count
            })
            logger.warning(f"[INTEGRITY] Found {count} orphaned KB chunks")

            if self.fix_mode:
                result = await self.db.kb_chunks.delete_many(
                    {"document_id": {"$nin": list(valid_doc_ids)}}
                )
                self.fixes.append({
                    "type": "DELETED_ORPHANED_KB_CHUNKS",
                    "count": result.deleted_count
                })

    async def check_duplicate_external_ids(self):
        """Find duplicate external_ids within same tenant."""
        logger.info("Checking for duplicate external IDs...")

        pipeline = [
            {
                "$group": {
                    "_id": {"tenant_id": "$tenant_id", "external_id": "$external_id"},
                    "count": {"$sum": 1},
                    "ids": {"$push": "$id"}
                }
            },
            {
                "$match": {"count": {"$gt": 1}}
            },
            {"$limit": 10}
        ]

        duplicates = []
        async for dup in self.db.opportunities.aggregate(pipeline):
            duplicates.append({
                "tenant_id": dup["_id"]["tenant_id"],
                "external_id": dup["_id"]["external_id"],
                "count": dup["count"],
                "opportunity_ids": dup["ids"][:3]  # Sample
            })

        if duplicates:
            self.issues.append({
                "type": "DUPLICATE_EXTERNAL_IDS",
                "count": len(duplicates),
                "sample": duplicates[:5]
            })
            logger.warning(f"[INTEGRITY] Found {len(duplicates)} duplicate external_id groups")


async def main():
    parser = argparse.ArgumentParser(description="Check database referential integrity")
    parser.add_argument("--fix", action="store_true", help="Auto-fix orphaned records")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Connect to database
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "outpace_intelligence")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    try:
        checker = IntegrityChecker(db, fix_mode=args.fix)
        results = await checker.run_all_checks()

        if args.json:
            import json
            print(json.dumps(results, indent=2))
        else:
            print("\n" + "=" * 60)
            print(f"INTEGRITY CHECK RESULTS")
            print("=" * 60)
            print(f"Status: {results['status']}")
            print(f"Issues found: {results['issues_count']}")
            print(f"Fixes applied: {results['fixes_count']}")
            print(f"Duration: {results['duration_seconds']}s")

            if results['issues']:
                print("\nISSUES:")
                for issue in results['issues']:
                    print(f"  - {issue['type']}: {issue['count']} records")

            if results['fixes']:
                print("\nFIXES APPLIED:")
                for fix in results['fixes']:
                    print(f"  - {fix['type']}: {fix['count']} records")

            print("=" * 60)

        # Exit code based on issues
        sys.exit(1 if results['issues_count'] > 0 else 0)

    except Exception as e:
        logger.error(f"Error during integrity check: {e}")
        sys.exit(2)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
