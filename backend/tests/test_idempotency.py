"""
Idempotency Tests - Protection against double-submit.

These tests verify that operations are idempotent where appropriate:
- CREATE with same external_id returns existing (not error)
- PATCH is idempotent (same update twice succeeds)
- DELETE is idempotent (delete twice handles gracefully)

Run: pytest backend/tests/test_idempotency.py -v
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models import OpportunityCreate, OpportunitySource, TokenData
from backend.routes.opportunities import (
    create_opportunity,
    update_opportunity_status,
    delete_opportunity
)


# Test fixtures
TENANT_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def make_super_admin_token():
    """Create a super admin token for testing."""
    return TokenData(
        user_id=USER_ID,
        email="admin@test.com",
        role="super_admin",
        tenant_id=None
    )


def make_tenant_user_token(tenant_id: str = TENANT_ID):
    """Create a tenant user token for testing."""
    return TokenData(
        user_id=USER_ID,
        email="user@test.com",
        role="tenant_user",
        tenant_id=tenant_id
    )


def make_opportunity_doc(opp_id: str, external_id: str, tenant_id: str = TENANT_ID):
    """Create a complete opportunity document for mocking."""
    now = "2026-01-01T00:00:00+00:00"
    return {
        "id": opp_id,
        "tenant_id": tenant_id,
        "external_id": external_id,
        "title": "Test Opportunity",
        "description": "Test description",
        "agency": "Test Agency",
        "due_date": None,
        "estimated_value": "$100,000",
        "naics_code": "541511",
        "keywords": [],
        "source_type": "manual",
        "source_url": "",
        "raw_data": {},
        "client_status": "new",
        "client_notes": None,
        "client_tags": [],
        "is_archived": False,
        "score": 50,
        "ai_relevance_summary": None,
        "captured_date": now,
        "created_at": now,
        "updated_at": now
    }


class TestCreateIdempotency:
    """Test that create operations handle duplicates gracefully."""

    @pytest.mark.asyncio
    async def test_create_with_same_external_id_returns_existing(self):
        """
        POST twice with same external_id should return existing record.

        This is the idempotent behavior that protects against double-submit.
        First call creates, second call returns existing (not error).
        """
        external_id = f"idem-{uuid.uuid4()}"
        existing_id = str(uuid.uuid4())

        existing_doc = make_opportunity_doc(existing_id, external_id)

        test_data = OpportunityCreate(
            tenant_id=TENANT_ID,
            external_id=external_id,
            title="Test Opportunity",
            description="Test description",
            source_type=OpportunitySource.MANUAL
        )

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            # Simulate existing record found (duplicate)
            mock_db.opportunities.find_one = AsyncMock(return_value=existing_doc)
            mock_db.tenants.find_one = AsyncMock(return_value={
                "id": TENANT_ID,
                "scoring_weights": {}
            })
            mock_get_db.return_value = mock_db

            # Should return existing record, NOT raise error
            result = await create_opportunity(test_data, make_super_admin_token())

        # Verify we got back the EXISTING record
        assert result.id == existing_id
        assert result.external_id == external_id

        # Verify no insert was called (existing record returned)
        mock_db.opportunities.insert_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_new_record_when_no_duplicate(self):
        """
        POST with new external_id should create new record.

        Baseline test - new records are created normally.
        """
        external_id = f"new-{uuid.uuid4()}"

        test_data = OpportunityCreate(
            tenant_id=TENANT_ID,
            external_id=external_id,
            title="New Opportunity",
            description="New description",
            source_type=OpportunitySource.MANUAL
        )

        inserted_doc = None

        async def capture_insert(doc):
            nonlocal inserted_doc
            inserted_doc = doc.copy()

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            # No existing record
            mock_db.opportunities.find_one = AsyncMock(return_value=None)
            mock_db.tenants.find_one = AsyncMock(return_value={
                "id": TENANT_ID,
                "scoring_weights": {}
            })
            mock_db.opportunities.insert_one = AsyncMock(side_effect=capture_insert)
            mock_get_db.return_value = mock_db

            result = await create_opportunity(test_data, make_super_admin_token())

        # Verify new record was created
        assert result.external_id == external_id
        assert inserted_doc is not None
        assert inserted_doc["external_id"] == external_id


class TestPatchIdempotency:
    """Test that PATCH operations are idempotent."""

    @pytest.mark.asyncio
    async def test_patch_same_status_twice_succeeds(self):
        """
        PATCH status=pursuing twice should both succeed.

        Idempotent updates allow safe retries without error.
        """
        opp_id = str(uuid.uuid4())

        # Document already has status="pursuing" (first patch already applied)
        doc_with_status = make_opportunity_doc(opp_id, "ext-123")
        doc_with_status["client_status"] = "pursuing"

        update_data = {"client_status": "pursuing"}

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(side_effect=[
                doc_with_status,  # Access check
                doc_with_status   # After update
            ])
            mock_db.opportunities.update_one = AsyncMock()
            mock_get_db.return_value = mock_db

            # Second PATCH with same value should succeed
            result = await update_opportunity_status(
                opp_id,
                update_data,
                make_tenant_user_token()
            )

        # Should succeed without error
        assert result.client_status == "pursuing"

        # Update should still be called (no-op is fine)
        mock_db.opportunities.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_patch_multiple_fields_idempotent(self):
        """
        PATCH with same values multiple times is idempotent.

        Re-applying the same update should not cause errors or side effects.
        """
        opp_id = str(uuid.uuid4())

        # Document already has these values
        doc = make_opportunity_doc(opp_id, "ext-456")
        doc["client_status"] = "interested"
        doc["client_notes"] = "Important notes"
        doc["client_tags"] = ["priority", "review"]

        update_data = {
            "client_status": "interested",
            "client_notes": "Important notes",
            "client_tags": ["priority", "review"]
        }

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(side_effect=[doc, doc])
            mock_db.opportunities.update_one = AsyncMock()
            mock_get_db.return_value = mock_db

            # Re-applying same values should succeed
            result = await update_opportunity_status(
                opp_id,
                update_data,
                make_tenant_user_token()
            )

        assert result.client_status == "interested"
        assert result.client_notes == "Important notes"
        assert result.client_tags == ["priority", "review"]

    @pytest.mark.asyncio
    async def test_patch_archived_twice_succeeds(self):
        """
        Setting is_archived=True twice should both succeed.
        """
        opp_id = str(uuid.uuid4())

        doc = make_opportunity_doc(opp_id, "ext-789")
        doc["is_archived"] = True  # Already archived

        update_data = {"is_archived": True}

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(side_effect=[doc, doc])
            mock_db.opportunities.update_one = AsyncMock()
            mock_get_db.return_value = mock_db

            result = await update_opportunity_status(
                opp_id,
                update_data,
                make_tenant_user_token()
            )

        assert result.is_archived is True


class TestDeleteIdempotency:
    """Test that DELETE operations handle retries gracefully."""

    @pytest.mark.asyncio
    async def test_delete_twice_second_returns_404(self):
        """
        DELETE same record twice - second should return 404.

        This is the expected behavior: first DELETE succeeds,
        second DELETE returns 404 (record no longer exists).
        Both are valid outcomes for the client.
        """
        from fastapi import HTTPException

        opp_id = str(uuid.uuid4())

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            # Record not found (already deleted)
            mock_db.opportunities.find_one = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            # Second DELETE should return 404
            with pytest.raises(HTTPException) as exc_info:
                await delete_opportunity(opp_id, make_super_admin_token())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_delete_existing_succeeds(self):
        """
        DELETE existing record should succeed with 204.
        """
        opp_id = str(uuid.uuid4())
        doc = make_opportunity_doc(opp_id, "ext-del")

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=doc)
            mock_db.opportunities.delete_one = AsyncMock()
            mock_get_db.return_value = mock_db

            result = await delete_opportunity(opp_id, make_super_admin_token())

        # Should succeed (returns None for 204)
        assert result is None
        mock_db.opportunities.delete_one.assert_called_once_with({"id": opp_id})

    @pytest.mark.asyncio
    async def test_delete_is_safe_to_retry(self):
        """
        Verify that DELETE retry pattern is safe.

        Client can safely retry DELETE without causing harm:
        - First attempt: 204 (deleted)
        - Retry attempts: 404 (already gone)

        Both outcomes indicate success from client's perspective.
        """
        from fastapi import HTTPException

        opp_id = str(uuid.uuid4())
        doc = make_opportunity_doc(opp_id, "ext-retry")

        # First DELETE
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=doc)
            mock_db.opportunities.delete_one = AsyncMock()
            mock_get_db.return_value = mock_db

            result1 = await delete_opportunity(opp_id, make_super_admin_token())

        assert result1 is None  # 204 success

        # Second DELETE (retry)
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=None)  # Gone
            mock_get_db.return_value = mock_db

            with pytest.raises(HTTPException) as exc_info:
                await delete_opportunity(opp_id, make_super_admin_token())

        # 404 is acceptable for retry (record is gone, which is the goal)
        assert exc_info.value.status_code == 404
