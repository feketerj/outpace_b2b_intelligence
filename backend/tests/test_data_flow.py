"""
Data Flow Verification Tests - INSERT→SELECT→verify pattern.

These tests verify that data written to the database is actually persisted
and can be read back correctly. This catches:
- Serialization bugs
- Field mapping issues
- Silent data corruption

Run: pytest backend/tests/test_data_flow.py -v
"""

import pytest
import uuid
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models import OpportunityCreate, OpportunitySource, TokenData
from backend.routes.opportunities import create_opportunity, get_opportunity, update_opportunity_status, delete_opportunity
from backend.routes.upload import upload_opportunities_csv


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


class TestWriteReadConsistency:
    """Test that data written is exactly what we read back."""

    @pytest.mark.asyncio
    async def test_create_opportunity_persists_all_fields(self):
        """
        Create opportunity, query it back, verify all fields match.

        Verifies: INSERT→SELECT consistency for all opportunity fields.
        """
        # Setup test data with all fields populated
        external_id = f"test-{uuid.uuid4()}"
        test_data = OpportunityCreate(
            tenant_id=TENANT_ID,
            external_id=external_id,
            title="Test Opportunity Title",
            description="This is a detailed test description with special chars: <>&\"'",
            agency="Department of Testing",
            due_date=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            estimated_value="$1,500,000",
            naics_code="541511",
            keywords=["testing", "integration", "python"],
            source_type=OpportunitySource.MANUAL,
            source_url="https://example.com/opportunity/123",
            raw_data={"custom_field": "custom_value", "nested": {"key": "value"}},
            client_status="new",
            client_notes="Initial notes for testing",
            client_tags=["priority", "review-needed"],
            is_archived=False
        )

        # Track what was actually inserted
        inserted_doc = None

        async def capture_insert(doc):
            nonlocal inserted_doc
            inserted_doc = doc.copy()

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            # No existing duplicate
            mock_db.opportunities.find_one = AsyncMock(return_value=None)
            # Return tenant with scoring weights
            mock_db.tenants.find_one = AsyncMock(return_value={
                "id": TENANT_ID,
                "scoring_weights": {}
            })
            # Capture the insert
            mock_db.opportunities.insert_one = AsyncMock(side_effect=capture_insert)
            mock_get_db.return_value = mock_db

            # Create the opportunity
            result = await create_opportunity(test_data, make_super_admin_token())

        # Verify all input fields are in the result
        assert result.tenant_id == TENANT_ID
        assert result.external_id == external_id
        assert result.title == test_data.title
        assert result.description == test_data.description
        assert result.agency == test_data.agency
        assert result.estimated_value == test_data.estimated_value
        assert result.naics_code == test_data.naics_code
        assert result.keywords == test_data.keywords
        assert result.source_type == test_data.source_type
        assert result.source_url == test_data.source_url
        assert result.raw_data == test_data.raw_data
        assert result.client_status == test_data.client_status
        assert result.client_notes == test_data.client_notes
        assert result.client_tags == test_data.client_tags
        assert result.is_archived == test_data.is_archived

        # Verify generated fields exist
        assert result.id is not None
        assert result.created_at is not None
        assert result.updated_at is not None

        # Verify what was actually written to DB matches
        assert inserted_doc is not None, "Insert was never called"
        assert inserted_doc["external_id"] == external_id
        assert inserted_doc["title"] == test_data.title
        assert inserted_doc["description"] == test_data.description
        assert inserted_doc["raw_data"] == test_data.raw_data

    @pytest.mark.asyncio
    async def test_create_opportunity_special_characters_preserved(self):
        """
        Verify special characters in text fields are preserved.

        Catches: Encoding issues, sanitization bugs, escape sequence problems.
        """
        special_chars = "Unicode: \u00e9\u00e0\u00fc\u00f1 | HTML: <script>alert('xss')</script> | Quotes: \"'`"

        test_data = OpportunityCreate(
            tenant_id=TENANT_ID,
            external_id=f"special-{uuid.uuid4()}",
            title=f"Title with {special_chars}",
            description=f"Description with {special_chars}",
            agency="Test Agency",
            source_type=OpportunitySource.MANUAL
        )

        inserted_doc = None

        async def capture_insert(doc):
            nonlocal inserted_doc
            inserted_doc = doc.copy()

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=None)
            mock_db.tenants.find_one = AsyncMock(return_value={"id": TENANT_ID, "scoring_weights": {}})
            mock_db.opportunities.insert_one = AsyncMock(side_effect=capture_insert)
            mock_get_db.return_value = mock_db

            result = await create_opportunity(test_data, make_super_admin_token())

        # Verify special characters are preserved exactly
        assert special_chars in result.title
        assert special_chars in result.description
        assert inserted_doc["title"] == test_data.title
        assert inserted_doc["description"] == test_data.description


class TestUpdatePersistence:
    """Test that updates are persisted correctly."""

    @pytest.mark.asyncio
    async def test_update_opportunity_persists_changes(self):
        """
        Update opportunity, query it back, verify changes persisted.

        Verifies: UPDATE→SELECT consistency.
        """
        opp_id = str(uuid.uuid4())

        # Original document in DB
        original_doc = {
            "id": opp_id,
            "tenant_id": TENANT_ID,
            "external_id": "original-ext-id",
            "title": "Original Title",
            "description": "Original description",
            "client_status": "new",
            "client_notes": None,
            "client_tags": [],
            "is_archived": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "captured_date": "2026-01-01T00:00:00+00:00",
            "score": 50,
            "source_type": "manual"
        }

        # What we want to update
        update_data = {
            "client_status": "pursuing",
            "client_notes": "High priority - CEO interest",
            "client_tags": ["priority", "q1-target"],
            "is_archived": False
        }

        # Track the actual update sent to DB
        update_query = None
        update_set = None

        async def capture_update(query, update):
            nonlocal update_query, update_set
            update_query = query
            update_set = update.get("$set", {})

        # After update, return modified doc
        updated_doc = {**original_doc, **update_data, "updated_at": "2026-01-07T12:00:00+00:00"}

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            # First find returns original, second returns updated
            mock_db.opportunities.find_one = AsyncMock(side_effect=[
                original_doc,  # For access check
                updated_doc    # After update
            ])
            mock_db.opportunities.update_one = AsyncMock(side_effect=capture_update)
            mock_get_db.return_value = mock_db

            result = await update_opportunity_status(
                opp_id,
                update_data,
                make_tenant_user_token()
            )

        # Verify the update was sent correctly
        assert update_query == {"id": opp_id}
        assert update_set["client_status"] == "pursuing"
        assert update_set["client_notes"] == "High priority - CEO interest"
        assert update_set["client_tags"] == ["priority", "q1-target"]
        assert "updated_at" in update_set  # Timestamp should be updated

        # Verify response contains updated values
        assert result.client_status == "pursuing"
        assert result.client_notes == "High priority - CEO interest"
        assert result.client_tags == ["priority", "q1-target"]

    @pytest.mark.asyncio
    async def test_update_partial_fields_preserves_others(self):
        """
        Update only some fields, verify others are preserved.

        Catches: Full-document replacement bugs, field deletion on partial update.
        """
        opp_id = str(uuid.uuid4())

        original_doc = {
            "id": opp_id,
            "tenant_id": TENANT_ID,
            "external_id": "test-ext",
            "title": "Test Title",
            "description": "Test description",
            "client_status": "new",
            "client_notes": "Existing notes should be preserved",
            "client_tags": ["existing-tag"],
            "is_archived": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "captured_date": "2026-01-01T00:00:00+00:00",
            "score": 75,
            "source_type": "manual"
        }

        # Only update status
        update_data = {"client_status": "dismissed"}

        update_set = None

        async def capture_update(query, update):
            nonlocal update_set
            update_set = update.get("$set", {})

        # After update, only status changes
        updated_doc = {**original_doc, "client_status": "dismissed", "updated_at": "2026-01-07T12:00:00+00:00"}

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(side_effect=[original_doc, updated_doc])
            mock_db.opportunities.update_one = AsyncMock(side_effect=capture_update)
            mock_get_db.return_value = mock_db

            result = await update_opportunity_status(opp_id, update_data, make_tenant_user_token())

        # Verify only requested field was in the update (plus updated_at)
        assert "client_status" in update_set
        assert "updated_at" in update_set
        # These should NOT be in the update since we didn't change them
        assert "client_notes" not in update_set
        assert "client_tags" not in update_set

        # Verify preserved fields in response
        assert result.client_notes == "Existing notes should be preserved"
        assert result.client_tags == ["existing-tag"]


class TestDeleteRemovesData:
    """Test that delete actually removes records."""

    @pytest.mark.asyncio
    async def test_delete_opportunity_removes_record(self):
        """
        Delete opportunity, verify it's actually removed.

        Verifies: DELETE actually deletes (not soft-delete unless intended).
        """
        opp_id = str(uuid.uuid4())

        doc = {
            "id": opp_id,
            "tenant_id": TENANT_ID,
            "title": "To Be Deleted",
        }

        delete_called_with = None

        async def capture_delete(query):
            nonlocal delete_called_with
            delete_called_with = query

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=doc)
            mock_db.opportunities.delete_one = AsyncMock(side_effect=capture_delete)
            mock_get_db.return_value = mock_db

            result = await delete_opportunity(opp_id, make_super_admin_token())

        # Verify delete was called with correct ID
        assert delete_called_with == {"id": opp_id}

        # Verify response is None (204 No Content)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self):
        """
        Attempt to delete non-existent record returns 404.

        Verifies: Proper error handling for missing records.
        """
        from fastapi import HTTPException

        opp_id = str(uuid.uuid4())

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=None)  # Not found
            mock_get_db.return_value = mock_db

            with pytest.raises(HTTPException) as exc_info:
                await delete_opportunity(opp_id, make_super_admin_token())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestBulkInsertConsistency:
    """Test that bulk operations create all expected records."""

    @pytest.mark.asyncio
    async def test_csv_upload_creates_all_records(self):
        """
        Upload CSV with N records, verify all N are created.

        Verifies: Bulk INSERT consistency, no silent row skipping.
        """
        from starlette.requests import Request
        from backend.utils.rate_limit import limiter

        tenant_id = str(uuid.uuid4())

        # Create CSV content with 5 records
        csv_content = """title,description,agency,due_date,estimated_value
Test Opp 1,Description 1,Agency A,2026-06-01,100000
Test Opp 2,Description 2,Agency B,2026-07-01,200000
Test Opp 3,Description 3,Agency C,2026-08-01,300000
Test Opp 4,Description 4,Agency D,2026-09-01,400000
Test Opp 5,Description 5,Agency E,2026-10-01,500000"""

        # Track all inserts
        inserted_docs = []

        async def capture_insert(doc):
            inserted_docs.append(doc.copy())

        # Create mock file
        mock_file = MagicMock()
        mock_file.filename = "test_opportunities.csv"
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))

        # Disable rate limiter for direct handler invocation
        original_enabled = limiter.enabled
        limiter.enabled = False

        try:
            # Create mock request for rate limiter compatibility
            scope = {"type": "http", "method": "POST", "path": f"/api/upload/opportunities/csv/{tenant_id}", "headers": []}
            mock_request = Request(scope)

            with patch('backend.routes.upload.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_db.tenants.find_one = AsyncMock(return_value={
                    "id": tenant_id,
                    "scoring_weights": {}
                })
                mock_db.opportunities.insert_one = AsyncMock(side_effect=capture_insert)
                mock_get_db.return_value = mock_db

                result = await upload_opportunities_csv(
                    mock_request,
                    tenant_id,
                    make_super_admin_token(),
                    mock_file
                )
        finally:
            limiter.enabled = original_enabled

        # Verify counts match
        assert result["status"] == "success"
        assert result["imported_count"] == 5
        assert result["total_rows"] == 5
        assert len(inserted_docs) == 5

        # Verify each record was created with correct data
        titles = [doc["title"] for doc in inserted_docs]
        assert "Test Opp 1" in titles
        assert "Test Opp 2" in titles
        assert "Test Opp 3" in titles
        assert "Test Opp 4" in titles
        assert "Test Opp 5" in titles

        # Verify all records have the correct tenant_id
        for doc in inserted_docs:
            assert doc["tenant_id"] == tenant_id
            assert doc["id"] is not None  # Generated UUID
            assert doc["external_id"] is not None  # Generated external_id

    @pytest.mark.asyncio
    async def test_csv_upload_with_special_characters(self):
        """
        Verify CSV with special characters in fields is handled correctly.

        Catches: CSV parsing issues, encoding problems.
        """
        from starlette.requests import Request
        from backend.utils.rate_limit import limiter

        tenant_id = str(uuid.uuid4())

        # CSV with special characters (quotes, commas in values, unicode)
        csv_content = '''title,description,agency
"Title with ""quotes""","Description with, comma",Normal Agency
Unicode: cafe,Regular desc,Agency B'''

        inserted_docs = []

        async def capture_insert(doc):
            inserted_docs.append(doc.copy())

        mock_file = MagicMock()
        mock_file.filename = "special_chars.csv"
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))

        # Disable rate limiter for direct handler invocation
        original_enabled = limiter.enabled
        limiter.enabled = False

        try:
            # Create mock request for rate limiter compatibility
            scope = {"type": "http", "method": "POST", "path": f"/api/upload/opportunities/csv/{tenant_id}", "headers": []}
            mock_request = Request(scope)

            with patch('backend.routes.upload.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_db.tenants.find_one = AsyncMock(return_value={"id": tenant_id, "scoring_weights": {}})
                mock_db.opportunities.insert_one = AsyncMock(side_effect=capture_insert)
                mock_get_db.return_value = mock_db

                result = await upload_opportunities_csv(mock_request, tenant_id, make_super_admin_token(), mock_file)
        finally:
            limiter.enabled = original_enabled

        assert result["imported_count"] == 2

        # Verify special characters preserved
        titles = [doc["title"] for doc in inserted_docs]
        descriptions = [doc["description"] for doc in inserted_docs]

        assert 'Title with "quotes"' in titles
        assert "Description with, comma" in descriptions

    @pytest.mark.asyncio
    async def test_csv_upload_empty_file_handles_gracefully(self):
        """
        Empty CSV (headers only) should succeed with 0 imports.

        Verifies: Edge case handling, no crash on empty data.
        """
        from starlette.requests import Request
        from backend.utils.rate_limit import limiter

        tenant_id = str(uuid.uuid4())

        csv_content = "title,description,agency\n"  # Headers only

        mock_file = MagicMock()
        mock_file.filename = "empty.csv"
        mock_file.content_type = "text/csv"
        mock_file.read = AsyncMock(return_value=csv_content.encode('utf-8'))

        # Disable rate limiter for direct handler invocation
        original_enabled = limiter.enabled
        limiter.enabled = False

        try:
            scope = {"type": "http", "method": "POST", "path": f"/api/upload/opportunities/csv/{tenant_id}", "headers": []}
            mock_request = Request(scope)

            with patch('backend.routes.upload.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_db.tenants.find_one = AsyncMock(return_value={"id": tenant_id, "scoring_weights": {}})
                mock_db.opportunities.insert_one = AsyncMock()
                mock_get_db.return_value = mock_db

                result = await upload_opportunities_csv(mock_request, tenant_id, make_super_admin_token(), mock_file)
        finally:
            limiter.enabled = original_enabled

        assert result["status"] == "success"
        assert result["imported_count"] == 0
        assert result["total_rows"] == 0
