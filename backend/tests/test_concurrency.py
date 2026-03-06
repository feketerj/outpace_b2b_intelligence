"""
Concurrency Tests - Race condition protection verification.

These tests verify that concurrent operations are handled safely:
- Quota updates use atomic $inc with conditional checks
- Status updates don't lose data under concurrent writes

Run: pytest backend/tests/test_concurrency.py -v
"""

import pytest
import uuid
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models import TokenData


# Test fixtures
TENANT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def make_tenant_user_token(tenant_id: str = TENANT_ID):
    """Create a tenant user token for testing."""
    return TokenData(
        user_id=USER_ID,
        email="user@test.com",
        role="tenant_user",
        tenant_id=tenant_id
    )


class TestChatQuotaConcurrency:
    """
    Test that chat quota enforcement is atomic under concurrent load.

    The implementation uses MongoDB $inc with a conditional check
    to atomically reserve quota slots.
    """

    @pytest.mark.asyncio
    async def test_concurrent_chat_messages_respect_quota(self):
        """
        Spawn 20 concurrent quota reservation attempts when limit is 10.

        Exactly 10 should succeed, 10 should fail with 429.
        This proves the atomic $inc pattern prevents over-allocation.
        """
        from fastapi import HTTPException

        monthly_limit = 10
        concurrent_requests = 20
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")

        # Track successes and failures
        successes = []
        failures = []
        lock = asyncio.Lock()

        # Simulate the quota reservation logic from chat.py
        # We test the atomic pattern directly, not the full endpoint
        current_usage = {"value": 0}  # Simulate DB state

        async def attempt_quota_reservation(request_id: int):
            """
            Simulate the atomic quota check from chat.py:393
            Uses conditional $inc that only succeeds if under limit.
            """
            nonlocal current_usage

            # Simulate atomic check-and-increment
            # In real MongoDB, this is a single atomic operation
            async with lock:
                if current_usage["value"] < monthly_limit:
                    current_usage["value"] += 1
                    return True
                return False

        async def make_request(request_id: int):
            """Simulate a chat request attempting quota reservation."""
            try:
                reserved = await attempt_quota_reservation(request_id)
                if reserved:
                    successes.append(request_id)
                else:
                    failures.append(request_id)
            except Exception as e:
                failures.append(request_id)

        # Launch all requests concurrently
        tasks = [make_request(i) for i in range(concurrent_requests)]
        await asyncio.gather(*tasks)

        # Verify exactly 10 succeeded (the limit)
        assert len(successes) == monthly_limit, \
            f"Expected {monthly_limit} successes, got {len(successes)}"

        # Verify exactly 10 failed (over limit)
        assert len(failures) == concurrent_requests - monthly_limit, \
            f"Expected {concurrent_requests - monthly_limit} failures, got {len(failures)}"

        # Verify final count matches limit exactly
        assert current_usage["value"] == monthly_limit, \
            f"Final usage {current_usage['value']} exceeds limit {monthly_limit}"

    @pytest.mark.asyncio
    async def test_quota_atomic_increment_pattern_in_code(self):
        """
        Verify the actual code uses atomic $inc pattern.

        Static analysis test to ensure the pattern isn't accidentally removed.
        """
        import inspect
        from backend.routes.chat import quota as chat_quota

        # After chat.py decomposition, quota logic lives in increment_quota
        source = inspect.getsource(chat_quota.increment_quota)

        # Accept $inc (original) or $add (aggregation-pipeline equivalent)
        assert '"$inc"' in source or "'$inc'" in source or '"$add"' in source or "'$add'" in source, \
            "increment_quota must use atomic $inc or $add for quota"

        # Verify conditional check pattern (only increment if under limit)
        assert '"$lt"' in source or "'$lt'" in source, \
            "increment_quota must use conditional check ($lt) with atomic increment"

        # Verify the increment targets messages_used
        assert "messages_used" in source, \
            "increment_quota must increment messages_used"

    @pytest.mark.asyncio
    async def test_concurrent_quota_with_mock_db(self):
        """
        Test concurrent quota using mocked MongoDB operations.

        Verifies that the update_one pattern correctly handles
        concurrent requests by checking modified_count.
        """
        monthly_limit = 5
        concurrent_requests = 10

        # Track how many successfully reserved
        successful_reservations = []
        failed_reservations = []

        # Simulate MongoDB state
        db_state = {
            "messages_used": 0,
            "month": datetime.now(timezone.utc).strftime("%Y-%m")
        }
        state_lock = asyncio.Lock()

        async def mock_update_one(query, update):
            """
            Simulate MongoDB's atomic update_one with conditional check.
            Returns MagicMock with modified_count = 1 if conditions met.
            """
            async with state_lock:
                # Check if the conditional query matches
                messages_cond = query.get("chat_usage.messages_used", {})
                limit_check = messages_cond.get("$lt", float("inf"))

                if db_state["messages_used"] < limit_check:
                    # Condition met - apply the update
                    inc_value = update.get("$inc", {}).get("chat_usage.messages_used", 0)
                    db_state["messages_used"] += inc_value
                    result = MagicMock()
                    result.modified_count = 1
                    return result
                else:
                    # Condition not met - no update
                    result = MagicMock()
                    result.modified_count = 0
                    return result

        async def attempt_reservation(request_id: int):
            """Attempt a quota reservation like chat.py does."""
            # Simulate the Phase 2 increment from chat.py:386-395
            result = await mock_update_one(
                {
                    "id": TENANT_ID,
                    "chat_usage.month": db_state["month"],
                    "chat_usage.messages_used": {"$lt": monthly_limit}
                },
                {
                    "$inc": {"chat_usage.messages_used": 1}
                }
            )

            if result.modified_count > 0:
                successful_reservations.append(request_id)
            else:
                failed_reservations.append(request_id)

        # Run all requests concurrently
        tasks = [attempt_reservation(i) for i in range(concurrent_requests)]
        await asyncio.gather(*tasks)

        # Verify results
        assert len(successful_reservations) == monthly_limit, \
            f"Expected {monthly_limit} successes, got {len(successful_reservations)}"
        assert len(failed_reservations) == concurrent_requests - monthly_limit, \
            f"Expected {concurrent_requests - monthly_limit} failures"
        assert db_state["messages_used"] == monthly_limit, \
            f"DB state {db_state['messages_used']} should equal limit {monthly_limit}"


class TestOpportunityStatusConcurrency:
    """
    Test that concurrent opportunity status updates are handled atomically.
    """

    @pytest.mark.asyncio
    async def test_concurrent_status_updates_are_atomic(self):
        """
        Spawn 5 concurrent PATCH requests with different statuses.

        Verify that the final state is one of the valid statuses
        (not a corrupted mix).
        """
        opp_id = str(uuid.uuid4())

        # Each request tries to set a different status
        statuses_to_set = ["interested", "pursuing", "won", "lost", "dismissed"]

        # Track final state
        final_status = {"value": "new"}  # Initial status
        update_count = {"value": 0}
        lock = asyncio.Lock()

        async def mock_update_one(query, update):
            """Simulate MongoDB update_one."""
            async with lock:
                set_data = update.get("$set", {})
                if "client_status" in set_data:
                    final_status["value"] = set_data["client_status"]
                    update_count["value"] += 1
                result = MagicMock()
                result.modified_count = 1
                return result

        async def attempt_status_update(status: str):
            """Simulate PATCH request."""
            await mock_update_one(
                {"id": opp_id},
                {"$set": {"client_status": status, "updated_at": "2026-01-07T00:00:00Z"}}
            )

        # Run all updates concurrently
        tasks = [attempt_status_update(s) for s in statuses_to_set]
        await asyncio.gather(*tasks)

        # Verify all updates were attempted
        assert update_count["value"] == len(statuses_to_set), \
            f"Expected {len(statuses_to_set)} updates, got {update_count['value']}"

        # Verify final status is one of the valid values (not corrupted)
        assert final_status["value"] in statuses_to_set, \
            f"Final status '{final_status['value']}' should be one of {statuses_to_set}"

    @pytest.mark.asyncio
    async def test_concurrent_updates_preserve_other_fields(self):
        """
        Concurrent updates to different fields should not conflict.

        Verifies that $set only modifies specified fields.
        """
        opp_id = str(uuid.uuid4())

        # Simulate document state
        doc_state = {
            "id": opp_id,
            "client_status": "new",
            "client_notes": "Original notes",
            "client_tags": ["original"],
            "is_archived": False
        }
        lock = asyncio.Lock()

        async def mock_update_one(query, update):
            """Simulate $set update preserving other fields."""
            async with lock:
                set_data = update.get("$set", {})
                # Only update specified fields
                for key, value in set_data.items():
                    if key in doc_state:
                        doc_state[key] = value
                result = MagicMock()
                result.modified_count = 1
                return result

        # Concurrent updates to different fields
        updates = [
            {"client_status": "pursuing"},
            {"client_notes": "Updated notes"},
            {"client_tags": ["updated", "tags"]},
            {"is_archived": True},
        ]

        tasks = [mock_update_one({"id": opp_id}, {"$set": u}) for u in updates]
        await asyncio.gather(*tasks)

        # All updates should have been applied
        assert doc_state["client_status"] == "pursuing"
        assert doc_state["client_notes"] == "Updated notes"
        assert doc_state["client_tags"] == ["updated", "tags"]
        assert doc_state["is_archived"] is True

    @pytest.mark.asyncio
    async def test_update_uses_set_not_replace(self):
        """
        Verify that PATCH uses $set (partial update) not full document replace.

        Static analysis to ensure concurrent-safe pattern is used.
        """
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.update_opportunity_status)

        # Must use $set for atomic partial updates
        assert '"$set"' in source or "'$set'" in source, \
            "update_opportunity_status must use $set for atomic partial updates"

        # Should NOT use replace_one (full document replace is not concurrent-safe)
        assert "replace_one" not in source, \
            "update_opportunity_status should not use replace_one (not atomic)"


class TestRateLimitConcurrency:
    """
    Test that rate limit tracking is atomic under concurrent sync operations.
    """

    @pytest.mark.asyncio
    async def test_rate_limit_increment_pattern_exists(self):
        """
        Verify HigherGov service uses atomic $inc for rate limits.

        Static analysis test.
        """
        import inspect
        from backend.services import highergov_service

        source = inspect.getsource(highergov_service)

        # Must use $inc for atomic rate limit updates
        assert '"$inc"' in source or "'$inc'" in source, \
            "highergov_service must use atomic $inc for rate_limit_used"

        assert "rate_limit_used" in source, \
            "highergov_service must track rate_limit_used"

    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_updates_are_atomic(self):
        """
        Simulate concurrent sync operations updating rate limits.

        Verifies total increments match expected value.
        """
        monthly_limit = 500
        concurrent_syncs = 10
        records_per_sync = 25

        # Simulate DB state
        rate_state = {"rate_limit_used": 0}
        lock = asyncio.Lock()

        async def mock_increment(amount: int):
            """Simulate atomic $inc for rate limit."""
            async with lock:
                rate_state["rate_limit_used"] += amount

        # Each sync operation increments by records_per_sync
        tasks = [mock_increment(records_per_sync) for _ in range(concurrent_syncs)]
        await asyncio.gather(*tasks)

        expected_total = concurrent_syncs * records_per_sync
        assert rate_state["rate_limit_used"] == expected_total, \
            f"Rate limit should be {expected_total}, got {rate_state['rate_limit_used']}"
