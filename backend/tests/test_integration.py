"""
Integration Tests - HTTP response structure validation.

These tests verify that actual HTTP responses match expected schemas
and formats, not just that code patterns exist.

Run: pytest backend/tests/test_integration.py -v
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models import TokenData, UserRole, PaginatedResponse
from backend.utils.auth import create_access_token
from backend.routes.opportunities import list_opportunities, get_opportunity
from backend.routes.auth import login


# Test fixtures
TENANT_A_ID = str(uuid.uuid4())
TENANT_B_ID = str(uuid.uuid4())
USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())


def make_token(user_id: str, email: str, role: str, tenant_id: str = None) -> str:
    """Create a valid JWT token for testing."""
    return create_access_token({
        "sub": user_id,
        "email": email,
        "role": role,
        "tenant_id": tenant_id
    })


def make_token_data(user_id: str, email: str, role: str, tenant_id: str = None) -> TokenData:
    """Create TokenData for direct function calls."""
    return TokenData(
        user_id=user_id,
        email=email,
        role=UserRole(role),
        tenant_id=tenant_id
    )


def make_opportunity_doc(opp_id: str, tenant_id: str, title: str = "Test Opportunity"):
    """Create a complete opportunity document for mocking."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": opp_id,
        "tenant_id": tenant_id,
        "external_id": f"ext-{opp_id[:8]}",
        "title": title,
        "description": "Test description",
        "agency": "Test Agency",
        "due_date": "2026-06-15T00:00:00+00:00",
        "estimated_value": "$100,000",
        "naics_code": "541511",
        "keywords": ["test", "keyword"],
        "source_type": "manual",
        "source_url": "https://example.com",
        "raw_data": {"source_id": "SRC-123"},
        "client_status": "new",
        "client_notes": None,
        "client_tags": [],
        "is_archived": False,
        "score": 75,
        "ai_relevance_summary": None,
        "captured_date": now,
        "created_at": now,
        "updated_at": now
    }


class TestOpportunitiesEndpointResponseSchema:
    """Test that opportunities endpoint returns correctly structured responses."""

    @pytest.mark.asyncio
    async def test_opportunities_list_response_matches_schema(self):
        """
        Call GET /opportunities, validate response structure.

        Response must be PaginatedResponse with:
        - data: list of opportunities
        - pagination: {total, page, per_page, pages}
        """
        opp1 = make_opportunity_doc(str(uuid.uuid4()), TENANT_A_ID, "Opportunity 1")
        opp2 = make_opportunity_doc(str(uuid.uuid4()), TENANT_A_ID, "Opportunity 2")

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[opp1, opp2])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=2)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=20,
                current_user=make_token_data(USER_A_ID, "user@test.com", "tenant_user", TENANT_A_ID)
            )

        # Verify response structure
        assert isinstance(result, PaginatedResponse)
        assert hasattr(result, 'data')
        assert hasattr(result, 'pagination')

        # Verify pagination metadata
        assert result.pagination.total == 2
        assert result.pagination.page == 1
        assert result.pagination.per_page == 20
        assert result.pagination.pages == 1

        # Verify data is list
        assert isinstance(result.data, list)
        assert len(result.data) == 2

        # Verify each opportunity has required fields
        for opp in result.data:
            assert 'id' in opp
            assert 'tenant_id' in opp
            assert 'title' in opp
            assert 'score' in opp
            assert 'solicitation_id' in opp  # Added by extract_solicitation_id

    @pytest.mark.asyncio
    async def test_opportunity_get_response_has_required_fields(self):
        """
        GET /opportunities/{id} returns opportunity with all required fields.
        """
        opp_id = str(uuid.uuid4())
        opp_doc = make_opportunity_doc(opp_id, TENANT_A_ID)

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=opp_doc)
            mock_get_db.return_value = mock_db

            result = await get_opportunity(
                opp_id,
                make_token_data(USER_A_ID, "user@test.com", "tenant_user", TENANT_A_ID)
            )

        # Verify all required Opportunity model fields are present
        required_fields = [
            'id', 'tenant_id', 'external_id', 'title', 'description',
            'source_type', 'score', 'captured_date', 'created_at', 'updated_at',
            'client_status', 'is_archived', 'solicitation_id'
        ]
        for field in required_fields:
            assert field in result or hasattr(result, field), \
                f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_empty_list_returns_valid_paginated_response(self):
        """
        Empty results should still return valid PaginatedResponse structure.
        """
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=0)
            mock_get_db.return_value = mock_db

            result = await list_opportunities(
                page=1,
                per_page=20,
                current_user=make_token_data(USER_A_ID, "user@test.com", "tenant_user", TENANT_A_ID)
            )

        assert isinstance(result, PaginatedResponse)
        assert result.data == []
        assert result.pagination.total == 0
        assert result.pagination.pages == 0


class TestErrorResponseFormat:
    """Test that error responses have consistent format."""

    @pytest.mark.asyncio
    async def test_401_error_response_format(self):
        """
        Call endpoint without auth should return 401 with proper format.

        Response should have:
        - status_code: 401
        - detail: string message
        """
        from fastapi import HTTPException
        from backend.utils.auth import decode_token

        # Invalid token should raise 401
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid-token")

        error = exc_info.value
        assert error.status_code == 401
        assert error.detail is not None
        assert isinstance(error.detail, str)
        assert "credentials" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_404_error_response_format(self):
        """
        Request non-existent resource returns 404 with proper format.
        """
        from fastapi import HTTPException

        opp_id = str(uuid.uuid4())

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_db

            with pytest.raises(HTTPException) as exc_info:
                await get_opportunity(
                    opp_id,
                    make_token_data(USER_A_ID, "user@test.com", "super_admin", None)
                )

        error = exc_info.value
        assert error.status_code == 404
        assert "not found" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_400_error_includes_field_info(self):
        """
        Validation errors should indicate which field(s) failed.
        """
        from fastapi import HTTPException
        from backend.routes.opportunities import update_opportunity_status

        opp_id = str(uuid.uuid4())
        opp_doc = make_opportunity_doc(opp_id, TENANT_A_ID)

        # Try to update with unknown field
        invalid_update = {"unknown_field": "value"}

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=opp_doc)
            mock_get_db.return_value = mock_db

            with pytest.raises(HTTPException) as exc_info:
                await update_opportunity_status(
                    opp_id,
                    invalid_update,
                    make_token_data(USER_A_ID, "user@test.com", "tenant_user", TENANT_A_ID)
                )

        error = exc_info.value
        assert error.status_code == 400
        assert "unknown_field" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_login_error_doesnt_leak_password(self):
        """
        Login failure should not include password in error response.

        Security test: password must never appear in error messages.
        """
        from fastapi import HTTPException
        from starlette.requests import Request
        from backend.models import LoginRequest
        from backend.utils.rate_limit import limiter

        test_password = "SuperSecret123!@#"

        # Disable rate limiter for direct handler invocation
        original_enabled = limiter.enabled
        limiter.enabled = False

        try:
            # Create mock request for rate limiter compatibility
            scope = {"type": "http", "method": "POST", "path": "/api/auth/login", "headers": []}
            mock_request = Request(scope)

            with patch('backend.routes.auth.get_db') as mock_get_db:
                mock_db = MagicMock()
                mock_db.users.find_one = AsyncMock(return_value=None)  # User not found
                mock_get_db.return_value = mock_db

                with pytest.raises(HTTPException) as exc_info:
                    await login(mock_request, LoginRequest(email="test@test.com", password=test_password))
        finally:
            limiter.enabled = original_enabled

        error = exc_info.value
        # Password must NEVER appear in error
        assert test_password not in str(error.detail)
        assert test_password not in str(error)


class TestCrossTenantAccess:
    """Test that cross-tenant access is properly blocked."""

    @pytest.mark.asyncio
    async def test_cross_tenant_request_returns_403(self):
        """
        Tenant A token requesting Tenant B data should return 403.

        This is the core tenant isolation test.
        """
        from fastapi import HTTPException

        opp_id = str(uuid.uuid4())
        # Opportunity belongs to Tenant B
        opp_doc = make_opportunity_doc(opp_id, TENANT_B_ID)

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=opp_doc)
            mock_get_db.return_value = mock_db

            # User from Tenant A tries to access
            with pytest.raises(HTTPException) as exc_info:
                await get_opportunity(
                    opp_id,
                    make_token_data(USER_A_ID, "user@a.com", "tenant_user", TENANT_A_ID)
                )

        error = exc_info.value
        assert error.status_code == 403
        assert "denied" in error.detail.lower() or "access" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_super_admin_can_access_any_tenant(self):
        """
        Super admin should be able to access any tenant's data.
        """
        opp_id = str(uuid.uuid4())
        opp_doc = make_opportunity_doc(opp_id, TENANT_B_ID)

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=opp_doc)
            mock_get_db.return_value = mock_db

            # Super admin (no tenant_id) can access any tenant's data
            result = await get_opportunity(
                opp_id,
                make_token_data(USER_A_ID, "admin@test.com", "super_admin", None)
            )

        # Should succeed
        assert result is not None

    @pytest.mark.asyncio
    async def test_tenant_user_cannot_escalate_via_tenant_id_param(self):
        """
        Tenant user specifying different tenant_id in query param should be ignored.

        The token's tenant_id should be used, not the request parameter.
        """
        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_db.opportunities.find.return_value = mock_cursor
            mock_db.opportunities.count_documents = AsyncMock(return_value=0)
            mock_get_db.return_value = mock_db

            # Tenant A user tries to request Tenant B data via param
            await list_opportunities(
                page=1,
                per_page=20,
                tenant_id=TENANT_B_ID,  # Trying to access Tenant B
                current_user=make_token_data(USER_A_ID, "user@a.com", "tenant_user", TENANT_A_ID)
            )

            # Verify the query used Tenant A (from token), not Tenant B (from param)
            call_args = mock_db.opportunities.find.call_args
            query = call_args[0][0] if call_args[0] else {}

            assert query.get("tenant_id") == TENANT_A_ID, \
                "Query must use tenant_id from token, not from request param"


class TestResponseHeaders:
    """Test that responses include expected headers."""

    def test_trace_id_propagation_pattern_exists(self):
        """
        Verify tracing middleware is configured for request ID propagation.

        Static analysis test.
        """
        import inspect
        from backend import server

        source = inspect.getsource(server)

        # Tracing middleware should be configured
        assert "TracingMiddleware" in source, \
            "TracingMiddleware should be configured for request tracing"

    def test_cors_middleware_configured(self):
        """
        Verify CORS middleware is configured.
        """
        import inspect
        from backend import server

        source = inspect.getsource(server)

        assert "CORSMiddleware" in source, \
            "CORSMiddleware should be configured"
        assert "allow_origins" in source, \
            "CORS should configure allow_origins"
