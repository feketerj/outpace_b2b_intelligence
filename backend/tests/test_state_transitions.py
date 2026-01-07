"""
State Transition Guards - Verify status transitions follow valid paths.

These tests verify that:
1. Tenant status transitions are valid
2. Document status transitions are valid
3. Opportunity status transitions are valid

Run: pytest backend/tests/test_state_transitions.py -v
"""

import pytest
from fastapi import HTTPException


class TestTenantStatusTransitions:
    """Test tenant status transition validation."""

    def test_active_to_suspended_allowed(self):
        """ACTIVE -> SUSPENDED is a valid transition."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # Should not raise
        validate_tenant_status_transition("ACTIVE", "SUSPENDED")

    def test_active_to_inactive_allowed(self):
        """ACTIVE -> INACTIVE is a valid transition."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # Should not raise
        validate_tenant_status_transition("ACTIVE", "INACTIVE")

    def test_suspended_to_active_allowed(self):
        """SUSPENDED -> ACTIVE is a valid transition."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # Should not raise
        validate_tenant_status_transition("SUSPENDED", "ACTIVE")

    def test_suspended_to_inactive_allowed(self):
        """SUSPENDED -> INACTIVE is a valid transition."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # Should not raise
        validate_tenant_status_transition("SUSPENDED", "INACTIVE")

    def test_inactive_to_active_allowed(self):
        """INACTIVE -> ACTIVE (reactivation) is valid."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # Should not raise
        validate_tenant_status_transition("INACTIVE", "ACTIVE")

    def test_inactive_to_suspended_not_allowed(self):
        """INACTIVE -> SUSPENDED is NOT allowed (must activate first)."""
        from backend.utils.state_machines import validate_tenant_status_transition

        with pytest.raises(HTTPException) as exc_info:
            validate_tenant_status_transition("INACTIVE", "SUSPENDED")

        assert exc_info.value.status_code == 400
        assert "Invalid status transition" in exc_info.value.detail

    def test_same_status_is_noop(self):
        """Same status transition is allowed (no-op)."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # All these should not raise
        validate_tenant_status_transition("ACTIVE", "ACTIVE")
        validate_tenant_status_transition("SUSPENDED", "SUSPENDED")
        validate_tenant_status_transition("INACTIVE", "INACTIVE")


class TestDocumentStatusTransitions:
    """Test document (RAG) status transition validation."""

    def test_pending_to_processing_allowed(self):
        """pending -> processing is valid."""
        from backend.utils.state_machines import validate_document_status_transition

        validate_document_status_transition("pending", "processing")

    def test_processing_to_ready_allowed(self):
        """processing -> ready is valid."""
        from backend.utils.state_machines import validate_document_status_transition

        validate_document_status_transition("processing", "ready")

    def test_processing_to_failed_allowed(self):
        """processing -> failed is valid."""
        from backend.utils.state_machines import validate_document_status_transition

        validate_document_status_transition("processing", "failed")

    def test_ready_is_immutable(self):
        """ready -> anything is NOT allowed (immutable)."""
        from backend.utils.state_machines import validate_document_status_transition

        with pytest.raises(HTTPException) as exc_info:
            validate_document_status_transition("ready", "processing")

        assert exc_info.value.status_code == 400

        with pytest.raises(HTTPException):
            validate_document_status_transition("ready", "failed")

    def test_failed_to_processing_allowed(self):
        """failed -> processing (retry) is valid."""
        from backend.utils.state_machines import validate_document_status_transition

        validate_document_status_transition("failed", "processing")


class TestOpportunityStatusTransitions:
    """Test opportunity client_status transition validation."""

    def test_new_to_reviewing_allowed(self):
        """new -> reviewing is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("new", "reviewing")

    def test_new_to_pursuing_allowed(self):
        """new -> pursuing is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("new", "pursuing")

    def test_pursuing_to_won_allowed(self):
        """pursuing -> won is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("pursuing", "won")

    def test_pursuing_to_lost_allowed(self):
        """pursuing -> lost is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("pursuing", "lost")

    def test_lost_to_reviewing_allowed(self):
        """lost -> reviewing (re-open) is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("lost", "reviewing")

    def test_won_cannot_go_back(self):
        """won -> reviewing is NOT allowed."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        with pytest.raises(HTTPException) as exc_info:
            validate_opportunity_status_transition("won", "reviewing")

        assert exc_info.value.status_code == 400

    def test_archived_can_be_reopened(self):
        """archived -> new or reviewing is valid."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        validate_opportunity_status_transition("archived", "new")
        validate_opportunity_status_transition("archived", "reviewing")


class TestGenericTransitionValidator:
    """Test the generic transition validator."""

    def test_generic_validator_works(self):
        """Generic validator should work with custom transitions."""
        from backend.utils.state_machines import validate_transition

        custom_transitions = {
            "draft": {"submitted"},
            "submitted": {"approved", "rejected"},
            "approved": set(),
            "rejected": {"draft"},
        }

        # Valid transitions
        validate_transition("draft", "submitted", custom_transitions, "custom")
        validate_transition("submitted", "approved", custom_transitions, "custom")
        validate_transition("rejected", "draft", custom_transitions, "custom")

        # Invalid transition
        with pytest.raises(HTTPException):
            validate_transition("approved", "draft", custom_transitions, "custom")


class TestTransitionEdgeCases:
    """Test edge cases in transition validation."""

    def test_none_to_valid_status(self):
        """None/empty current status should default gracefully."""
        from backend.utils.state_machines import validate_opportunity_status_transition

        # None defaults to "new"
        validate_opportunity_status_transition(None, "reviewing")
        validate_opportunity_status_transition("", "reviewing")

    def test_case_insensitivity_for_tenant_status(self):
        """Tenant status validation should be case-insensitive."""
        from backend.utils.state_machines import validate_tenant_status_transition

        # These should all work
        validate_tenant_status_transition("active", "suspended")
        validate_tenant_status_transition("Active", "Suspended")
        validate_tenant_status_transition("ACTIVE", "SUSPENDED")
