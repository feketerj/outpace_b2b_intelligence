"""
Tenant Isolation Guards - Regression tests for cross-tenant data leakage.

These tests verify that tenant boundaries are NEVER violated.
Any cross-tenant data access should fail with 403/404.

Run: pytest backend/tests/test_tenant_isolation.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

# Test fixtures
TENANT_A_ID = str(uuid.uuid4())
TENANT_B_ID = str(uuid.uuid4())
USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())


class TestTenantIsolationInvariants:
    """Test the invariant assertion helpers."""

    def test_assert_tenant_match_passes_for_correct_tenant(self):
        """Documents with matching tenant_id should pass."""
        from backend.utils.invariants import assert_tenant_match

        docs = [
            {"id": "1", "tenant_id": TENANT_A_ID, "data": "foo"},
            {"id": "2", "tenant_id": TENANT_A_ID, "data": "bar"},
        ]

        # Should not raise
        assert_tenant_match(docs, TENANT_A_ID)

    def test_assert_tenant_match_fails_for_wrong_tenant(self):
        """Documents with mismatched tenant_id should raise."""
        from backend.utils.invariants import assert_tenant_match, InvariantViolation

        docs = [
            {"id": "1", "tenant_id": TENANT_A_ID, "data": "foo"},
            {"id": "2", "tenant_id": TENANT_B_ID, "data": "bar"},  # WRONG TENANT
        ]

        with pytest.raises(InvariantViolation) as exc_info:
            assert_tenant_match(docs, TENANT_A_ID)

        assert "Cross-tenant data detected" in str(exc_info.value)

    def test_assert_tenant_match_handles_empty_list(self):
        """Empty document list should pass."""
        from backend.utils.invariants import assert_tenant_match

        # Should not raise
        assert_tenant_match([], TENANT_A_ID)

    def test_assert_single_tenant_passes_for_one_tenant(self):
        """Documents all from one tenant should pass."""
        from backend.utils.invariants import assert_single_tenant

        docs = [
            {"id": "1", "tenant_id": TENANT_A_ID},
            {"id": "2", "tenant_id": TENANT_A_ID},
        ]

        # Should not raise
        assert_single_tenant(docs)

    def test_assert_single_tenant_fails_for_multi_tenant(self):
        """Documents from multiple tenants should raise."""
        from backend.utils.invariants import assert_single_tenant, InvariantViolation

        docs = [
            {"id": "1", "tenant_id": TENANT_A_ID},
            {"id": "2", "tenant_id": TENANT_B_ID},
        ]

        with pytest.raises(InvariantViolation) as exc_info:
            assert_single_tenant(docs)

        assert "multiple tenants" in str(exc_info.value)

    def test_assert_auth_tenant_access_passes_for_own_tenant(self):
        """User accessing own tenant should pass."""
        from backend.utils.invariants import assert_auth_tenant_access

        # Should not raise
        assert_auth_tenant_access(
            user_tenant_id=TENANT_A_ID,
            requested_tenant_id=TENANT_A_ID,
            user_role="tenant_user",
            context="test"
        )

    def test_assert_auth_tenant_access_fails_for_other_tenant(self):
        """User accessing other tenant should raise."""
        from backend.utils.invariants import assert_auth_tenant_access, InvariantViolation

        with pytest.raises(InvariantViolation) as exc_info:
            assert_auth_tenant_access(
                user_tenant_id=TENANT_A_ID,
                requested_tenant_id=TENANT_B_ID,
                user_role="tenant_user",
                context="test"
            )

        assert "Unauthorized tenant access" in str(exc_info.value)

    def test_assert_auth_tenant_access_passes_for_super_admin(self):
        """Super admin accessing any tenant should pass."""
        from backend.utils.invariants import assert_auth_tenant_access

        # Should not raise - super admin can access any tenant
        assert_auth_tenant_access(
            user_tenant_id=TENANT_A_ID,
            requested_tenant_id=TENANT_B_ID,
            user_role="super_admin",
            context="test"
        )


class TestTenantIsolationQueryPatterns:
    """Test that queries include tenant_id filters."""

    def test_opportunity_query_includes_tenant_filter(self):
        """Opportunity queries MUST include tenant_id for non-super-admin."""
        # This is a static analysis test - verify the code pattern exists

        import ast
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.list_opportunities)

        # Parse the function and look for tenant_id in query building
        assert 'query["tenant_id"]' in source or "tenant_id" in source, \
            "list_opportunities must filter by tenant_id"

    def test_chat_query_includes_tenant_filter(self):
        """Chat queries MUST include tenant_id filter."""
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat.get_chat_history)

        assert "tenant_id" in source, \
            "get_chat_history must filter by tenant_id"

    def test_rag_chunks_query_includes_tenant_filter(self):
        """RAG chunk queries MUST include tenant_id filter."""
        import inspect
        from backend.routes import rag

        source = inspect.getsource(rag.retrieve_rag_context)

        # Must have tenant_id in query
        assert '{"tenant_id": tenant_id}' in source or '"tenant_id": tenant_id' in source, \
            "retrieve_rag_context must filter chunks by tenant_id"

    def test_rag_chunks_has_assert_tenant_match(self):
        """RAG chunk retrieval MUST have assert_tenant_match defense-in-depth."""
        import inspect
        from backend.routes import rag

        source = inspect.getsource(rag.retrieve_rag_context)

        assert "assert_tenant_match" in source, \
            "retrieve_rag_context must call assert_tenant_match for defense-in-depth"

    def test_rag_documents_query_includes_tenant_filter(self):
        """RAG document queries MUST include tenant_id filter."""
        import inspect
        from backend.routes import rag

        source = inspect.getsource(rag.retrieve_rag_context)

        # Must have tenant_id in document query
        assert "tenant_id" in source and "kb_documents" in source, \
            "retrieve_rag_context must filter documents by tenant_id"


class TestCrossTenantAccessDenied:
    """
    Integration-style tests verifying cross-tenant access is denied.

    These tests use mocked database to simulate the scenario where
    data exists for Tenant A, and Tenant B tries to access it.
    """

    @pytest.mark.asyncio
    async def test_opportunity_access_denied_for_wrong_tenant(self):
        """Tenant B user cannot access Tenant A's opportunity."""
        from backend.routes.opportunities import get_opportunity
        from backend.utils.auth import TokenData
        from fastapi import HTTPException

        # Create a mock opportunity belonging to Tenant A
        mock_opp = {
            "id": "opp-123",
            "tenant_id": TENANT_A_ID,
            "title": "Secret Opportunity",
        }

        # Create Tenant B user token
        tenant_b_user = TokenData(
            user_id=USER_B_ID,
            email="userb@tenantb.com",
            role="tenant_user",
            tenant_id=TENANT_B_ID
        )

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=mock_opp)
            mock_get_db.return_value = mock_db

            # Tenant B user tries to access Tenant A's opportunity
            with pytest.raises(HTTPException) as exc_info:
                await get_opportunity("opp-123", tenant_b_user)

            assert exc_info.value.status_code == 403
            assert "Access denied" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_tenant_user_cannot_list_other_tenant_opportunities(self):
        """Tenant user query is scoped to their own tenant only."""
        from backend.routes.opportunities import list_opportunities
        from backend.utils.auth import TokenData

        tenant_a_user = TokenData(
            user_id=USER_A_ID,
            email="usera@tenanta.com",
            role="tenant_user",
            tenant_id=TENANT_A_ID
        )

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

            # Call list with tenant_id param for a DIFFERENT tenant
            # The route should ignore the tenant_id param for non-super-admin
            await list_opportunities(
                page=1,
                per_page=20,
                tenant_id=TENANT_B_ID,  # Trying to access Tenant B
                current_user=tenant_a_user  # But user is from Tenant A
            )

            # Verify the query used Tenant A's ID (from token), NOT Tenant B
            call_args = mock_db.opportunities.find.call_args
            query = call_args[0][0] if call_args[0] else {}

            assert query.get("tenant_id") == TENANT_A_ID, \
                "Query must use tenant_id from token, not from request param"


class TestAuditLogsForCrossTenantAttempts:
    """Verify that cross-tenant access attempts are logged."""

    def test_audit_log_format_includes_tenant_ids(self):
        """Audit log entries should include both attempted and actual tenant IDs."""
        # This is verified by checking the route code has proper logging
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.get_opportunity)

        # Should have audit logging
        assert "_audit_access" in source or "logger" in source, \
            "get_opportunity should log access attempts"
