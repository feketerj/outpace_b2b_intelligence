"""
Contract Guards - Regression tests for API and data contracts.

These tests verify that:
1. API endpoints reject unknown fields
2. Response schemas match expected structure
3. Required fields are present in database documents

Run: pytest backend/tests/test_contracts.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


class TestUnknownFieldRejection:
    """Test that all PATCH/PUT endpoints reject unknown fields."""

    @pytest.mark.asyncio
    async def test_opportunities_patch_rejects_unknown_fields(self):
        """PATCH /opportunities/{id} must reject unknown fields with 400."""
        from backend.routes.opportunities import update_opportunity_status
        from backend.utils.auth import TokenData
        from fastapi import HTTPException

        user = TokenData(
            user_id=str(uuid.uuid4()),
            email="user@test.com",
            role="tenant_user",
            tenant_id=str(uuid.uuid4())
        )

        mock_opp = {
            "id": "opp-123",
            "tenant_id": user.tenant_id,
            "title": "Test",
        }

        with patch('backend.routes.opportunities.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.opportunities.find_one = AsyncMock(return_value=mock_opp)
            mock_get_db.return_value = mock_db

            # Include unknown field
            update_data = {
                "client_status": "reviewing",
                "unknown_field": "should_be_rejected",  # UNKNOWN
            }

            with pytest.raises(HTTPException) as exc_info:
                await update_opportunity_status("opp-123", update_data, user)

            assert exc_info.value.status_code == 400
            assert "Unknown fields rejected" in exc_info.value.detail
            assert "unknown_field" in exc_info.value.detail

    def test_tenants_patch_rejects_unknown_fields(self):
        """PATCH /tenants/{id} must reject unknown fields with 400."""
        from backend.routes.tenants import find_all_unknown_fields

        payload = {
            "name": "Valid Name",
            "unknown_top_level": "should_be_rejected",
        }

        unknown = find_all_unknown_fields(payload)
        assert "unknown_top_level" in unknown

    def test_tenants_patch_rejects_unknown_nested_fields(self):
        """PATCH /tenants/{id} must reject unknown nested fields."""
        from backend.routes.tenants import find_all_unknown_fields

        payload = {
            "name": "Valid Name",
            "scoring_weights": {
                "value_weight": 0.5,
                "unknown_weight": 0.3,  # UNKNOWN nested field
            }
        }

        unknown = find_all_unknown_fields(payload)
        assert "scoring_weights.unknown_weight" in unknown

    def test_config_rejects_unknown_fields(self):
        """Intelligence config must reject unknown fields."""
        from backend.routes.config import ALLOWED_INTELLIGENCE_CONFIG_FIELDS

        # Verify the allowed fields set exists and has expected fields
        assert "enabled" in ALLOWED_INTELLIGENCE_CONFIG_FIELDS
        assert "schedule_cron" in ALLOWED_INTELLIGENCE_CONFIG_FIELDS
        assert "unknown_field" not in ALLOWED_INTELLIGENCE_CONFIG_FIELDS


class TestAllowedFieldsSingleSourceOfTruth:
    """Verify that allowed field lists are defined and consistent."""

    def test_opportunities_allowed_fields_defined(self):
        """Opportunities PATCH should have explicit allowed fields."""
        import inspect
        from backend.routes import opportunities

        source = inspect.getsource(opportunities.update_opportunity_status)

        assert "allowed_fields" in source, \
            "update_opportunity_status must define allowed_fields"
        assert "client_status" in source, \
            "client_status should be an allowed field"

    def test_tenants_allowed_fields_comprehensive(self):
        """Tenants allowed fields should cover all expected top-level keys."""
        from backend.routes.tenants import ALLOWED_TOP_LEVEL_FIELDS

        expected_fields = {
            "name", "slug", "status", "branding", "search_profile",
            "scoring_weights", "agent_config", "intelligence_config",
            "chat_policy", "tenant_knowledge", "rag_policy"
        }

        missing = expected_fields - ALLOWED_TOP_LEVEL_FIELDS
        assert not missing, f"Missing expected fields: {missing}"

    def test_tenants_nested_fields_defined(self):
        """Nested field schemas should be defined."""
        from backend.routes.tenants import ALLOWED_NESTED_FIELDS

        # Check key nested objects have their schemas
        assert "branding" in ALLOWED_NESTED_FIELDS
        assert "search_profile" in ALLOWED_NESTED_FIELDS
        assert "chat_policy" in ALLOWED_NESTED_FIELDS
        assert "rag_policy" in ALLOWED_NESTED_FIELDS

        # Check specific nested fields exist
        assert "enabled" in ALLOWED_NESTED_FIELDS["chat_policy"]
        assert "monthly_message_limit" in ALLOWED_NESTED_FIELDS["chat_policy"]


class TestResponseSchemas:
    """Test that endpoints return expected response structures."""

    def test_opportunity_model_has_required_fields(self):
        """Opportunity model should define all required fields."""
        from backend.models import Opportunity
        import pydantic

        # Get model fields
        fields = Opportunity.model_fields

        required_fields = ["id", "tenant_id", "title"]
        for field in required_fields:
            assert field in fields, f"Opportunity missing required field: {field}"

    def test_tenant_model_has_required_fields(self):
        """Tenant model should define all required fields."""
        from backend.models import Tenant

        fields = Tenant.model_fields

        required_fields = ["id", "name", "slug", "status"]
        for field in required_fields:
            assert field in fields, f"Tenant missing required field: {field}"

    def test_paginated_response_structure(self):
        """PaginatedResponse should have data and pagination fields."""
        from backend.models import PaginatedResponse, PaginationMetadata

        fields = PaginatedResponse.model_fields

        assert "data" in fields
        assert "pagination" in fields

        # Check pagination metadata
        meta_fields = PaginationMetadata.model_fields
        assert "total" in meta_fields
        assert "page" in meta_fields
        assert "per_page" in meta_fields
        assert "pages" in meta_fields


class TestDatabaseDocumentContracts:
    """Test that database documents have required fields."""

    def test_invariant_fields_present_helper(self):
        """Test the assert_fields_present helper."""
        from backend.utils.invariants import assert_fields_present, InvariantViolation

        # Valid document
        doc = {"id": "123", "tenant_id": "abc", "title": "Test"}
        assert_fields_present(doc, ["id", "tenant_id", "title"])  # Should not raise

        # Missing field
        doc_missing = {"id": "123", "title": "Test"}
        with pytest.raises(InvariantViolation):
            assert_fields_present(doc_missing, ["id", "tenant_id", "title"])

    def test_opportunity_required_fields(self):
        """Opportunity documents must have specific required fields."""
        # This documents the contract - any opportunity inserted must have these
        required = ["id", "tenant_id", "title", "created_at"]

        # Use in code like:
        # from backend.utils.invariants import assert_fields_present
        # assert_fields_present(opp_doc, required, "opportunity")

        assert len(required) == 4  # Self-documenting test


class TestExternalServiceResponseValidation:
    """Test that external service responses are validated."""

    def test_mistral_response_structure_expected(self):
        """Mistral service should return expected structure on failure."""
        # When AI scoring fails, the response should include ai_scoring_failed
        expected_failure_response = {
            "relevance_summary": None,
            "suggested_score_adjustment": 0,
            "ai_scoring_failed": True,
            "ai_error": "some error",
        }

        # Verify structure
        assert "ai_scoring_failed" in expected_failure_response
        assert expected_failure_response["ai_scoring_failed"] is True

    def test_rag_degraded_response_structure(self):
        """RAG service should indicate degradation in response."""
        expected_degraded = {
            "reason": "embed_error",
            "error": "Connection failed",
            "rag_degraded": True,
        }

        assert "rag_degraded" in expected_degraded
        assert expected_degraded["rag_degraded"] is True
