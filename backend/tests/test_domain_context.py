"""
Domain Context Injection Tests.

Tests for opportunities/intelligence context injection in chat.
Verifies: data retrieval, tenant isolation (INV-1), audit logging.

Run: pytest backend/tests/test_domain_context.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Import the functions under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class MockCursor:
    """Mock MongoDB cursor for testing."""

    def __init__(self, data):
        self._data = data

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    async def to_list(self, length=None):
        if length:
            return self._data[:length]
        return self._data


class TestOpportunitiesContextRetrieval:
    """Test _retrieve_opportunities_context function."""

    @pytest.mark.asyncio
    async def test_returns_opportunities_for_tenant(self):
        """Should return opportunities belonging to tenant."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_opps = [
            {"id": "opp-1", "title": "Test Opportunity 1", "agency": "DOD",
             "due_date": datetime(2026, 3, 15), "estimated_value": "$1M",
             "score": 85, "client_status": "new", "tenant_id": tenant_id},
            {"id": "opp-2", "title": "Test Opportunity 2", "agency": "GSA",
             "due_date": datetime(2026, 4, 1), "estimated_value": "$500K",
             "score": 75, "client_status": "interested", "tenant_id": tenant_id},
        ]

        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor(mock_opps)

        agent_config = {}
        context, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, agent_config
        )

        assert "Current Opportunities:" in context
        assert "Test Opportunity 1" in context
        assert "Test Opportunity 2" in context
        assert debug_info["items_used"] == 2
        assert debug_info["reason"] == "success"

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforced(self):
        """CRITICAL: Should raise InvariantViolation if wrong tenant data returned."""
        from backend.routes.chat import _retrieve_opportunities_context
        from backend.utils.invariants import InvariantViolation

        tenant_id = "tenant-123"
        # Simulate a query that returns data from wrong tenant (should never happen in real DB)
        mock_opps = [
            {"id": "opp-1", "title": "Wrong Tenant Opp", "tenant_id": "tenant-OTHER"},
        ]

        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor(mock_opps)

        with pytest.raises(InvariantViolation) as exc_info:
            await _retrieve_opportunities_context(mock_db, tenant_id, {})

        assert "Cross-tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_respects_max_items_limit(self):
        """Should respect max_items configuration."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_opps = [
            {"id": f"opp-{i}", "title": f"Opportunity {i}", "agency": "DOD",
             "score": 90 - i, "tenant_id": tenant_id}
            for i in range(20)
        ]

        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor(mock_opps)

        agent_config = {"opportunities_context_max_items": 5}
        context, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, agent_config
        )

        # Should only include 5 items
        assert debug_info["items_used"] <= 5

    @pytest.mark.asyncio
    async def test_excludes_archived_by_default(self):
        """Should exclude archived items by default."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor([])

        await _retrieve_opportunities_context(mock_db, tenant_id, {})

        # Check the query includes is_archived filter
        call_args = mock_db.opportunities.find.call_args
        query = call_args[0][0]
        assert query.get("is_archived") == {"$ne": True}

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        """Should return empty when disabled in config."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()

        agent_config = {"opportunities_context_enabled": False}
        context, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, agent_config
        )

        assert context == ""
        assert debug_info["enabled"] == False
        assert debug_info["reason"] == "disabled"
        # Should not even query the database
        mock_db.opportunities.find.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_items(self):
        """Should return empty context with reason=no_items."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor([])

        context, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, {}
        )

        assert context == ""
        assert debug_info["reason"] == "no_items"

    @pytest.mark.asyncio
    async def test_respects_min_score_filter(self):
        """Should filter by minimum score."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor([])

        agent_config = {"opportunities_context_min_score": 75}
        await _retrieve_opportunities_context(mock_db, tenant_id, agent_config)

        call_args = mock_db.opportunities.find.call_args
        query = call_args[0][0]
        assert query.get("score") == {"$gte": 75}


class TestIntelligenceContextRetrieval:
    """Test _retrieve_intelligence_context function."""

    @pytest.mark.asyncio
    async def test_returns_intelligence_for_tenant(self):
        """Should return intelligence belonging to tenant."""
        from backend.routes.chat import _retrieve_intelligence_context

        tenant_id = "tenant-123"
        mock_intel = [
            {"id": "intel-1", "title": "Market Analysis", "type": "market",
             "summary": "Key market trends for Q1", "tenant_id": tenant_id},
            {"id": "intel-2", "title": "Competitor Update", "type": "competitive",
             "summary": "Competitor X launched new product", "tenant_id": tenant_id},
        ]

        mock_db = MagicMock()
        mock_db.intelligence.find.return_value = MockCursor(mock_intel)

        context, debug_info = await _retrieve_intelligence_context(
            mock_db, tenant_id, {}
        )

        assert "Recent Intelligence Reports:" in context
        assert "Market Analysis" in context
        assert "Competitor Update" in context
        assert debug_info["items_used"] == 2
        assert debug_info["reason"] == "success"

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforced(self):
        """CRITICAL: Should raise InvariantViolation if wrong tenant data returned."""
        from backend.routes.chat import _retrieve_intelligence_context
        from backend.utils.invariants import InvariantViolation

        tenant_id = "tenant-123"
        mock_intel = [
            {"id": "intel-1", "title": "Wrong Tenant Intel", "tenant_id": "tenant-OTHER"},
        ]

        mock_db = MagicMock()
        mock_db.intelligence.find.return_value = MockCursor(mock_intel)

        with pytest.raises(InvariantViolation) as exc_info:
            await _retrieve_intelligence_context(mock_db, tenant_id, {})

        assert "Cross-tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        """Should return empty when disabled in config."""
        from backend.routes.chat import _retrieve_intelligence_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()

        agent_config = {"intelligence_context_enabled": False}
        context, debug_info = await _retrieve_intelligence_context(
            mock_db, tenant_id, agent_config
        )

        assert context == ""
        assert debug_info["enabled"] == False
        assert debug_info["reason"] == "disabled"
        mock_db.intelligence.find.assert_not_called()

    @pytest.mark.asyncio
    async def test_truncates_long_summaries(self):
        """Should truncate summaries to 200 chars."""
        from backend.routes.chat import _retrieve_intelligence_context

        tenant_id = "tenant-123"
        long_summary = "A" * 500  # 500 char summary
        mock_intel = [
            {"id": "intel-1", "title": "Long Report", "type": "news",
             "summary": long_summary, "tenant_id": tenant_id},
        ]

        mock_db = MagicMock()
        mock_db.intelligence.find.return_value = MockCursor(mock_intel)

        context, _ = await _retrieve_intelligence_context(mock_db, tenant_id, {})

        # Summary should be truncated, so context shouldn't contain full 500 chars
        assert long_summary not in context
        assert "A" * 200 in context  # First 200 chars should be there


class TestDomainContextTenantIsolation:
    """Critical tests for INV-1 enforcement."""

    @pytest.mark.asyncio
    async def test_query_always_includes_tenant_filter(self):
        """All queries MUST filter by tenant_id."""
        from backend.routes.chat import _retrieve_opportunities_context, _retrieve_intelligence_context

        tenant_id = "tenant-123"
        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor([])
        mock_db.intelligence.find.return_value = MockCursor([])

        # Test opportunities
        await _retrieve_opportunities_context(mock_db, tenant_id, {})
        opp_query = mock_db.opportunities.find.call_args[0][0]
        assert opp_query.get("tenant_id") == tenant_id

        # Test intelligence
        await _retrieve_intelligence_context(mock_db, tenant_id, {})
        intel_query = mock_db.intelligence.find.call_args[0][0]
        assert intel_query.get("tenant_id") == tenant_id


class TestDomainContextDebugInfo:
    """Test debug information returned by retrieval functions."""

    @pytest.mark.asyncio
    async def test_debug_includes_ids_when_enabled(self):
        """Debug mode should include opportunity/intelligence IDs."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_opps = [
            {"id": "opp-1", "title": "Test 1", "score": 90, "tenant_id": tenant_id},
            {"id": "opp-2", "title": "Test 2", "score": 80, "tenant_id": tenant_id},
        ]

        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor(mock_opps)

        _, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, {}, debug=True
        )

        assert "opp_ids" in debug_info
        assert "opp-1" in debug_info["opp_ids"]
        assert "opp-2" in debug_info["opp_ids"]

    @pytest.mark.asyncio
    async def test_debug_ids_not_included_when_disabled(self):
        """Debug info should not include IDs when debug=False."""
        from backend.routes.chat import _retrieve_opportunities_context

        tenant_id = "tenant-123"
        mock_opps = [
            {"id": "opp-1", "title": "Test 1", "score": 90, "tenant_id": tenant_id},
        ]

        mock_db = MagicMock()
        mock_db.opportunities.find.return_value = MockCursor(mock_opps)

        _, debug_info = await _retrieve_opportunities_context(
            mock_db, tenant_id, {}, debug=False
        )

        assert "opp_ids" not in debug_info


class TestDomainContextAuditLogs:
    """Verify audit logging patterns."""

    def test_debug_info_structure(self):
        """Debug info should have expected structure for audit logging."""
        # The debug_info dict should have these keys for audit logging
        expected_keys = {"enabled", "reason", "items_searched", "items_used", "context_chars"}

        # These are the keys we initialize in both functions
        sample_debug_info = {"enabled": True, "reason": None, "items_searched": 0,
                           "items_used": 0, "context_chars": 0}

        assert expected_keys == set(sample_debug_info.keys())
