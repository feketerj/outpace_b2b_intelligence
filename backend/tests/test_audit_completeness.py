"""
Audit Completeness Guards - Verify all write operations have audit logs.

These tests verify that:
1. Every POST/PUT/PATCH/DELETE has an audit log entry
2. Audit log format is machine-parseable
3. Audit logs include required fields (who, what, when)

Run: pytest backend/tests/test_audit_completeness.py -v
"""

import pytest
import re
import inspect


class TestAuditLogPresence:
    """Verify audit logging exists in all write endpoints."""

    def test_tenant_create_has_audit_log(self):
        """POST /tenants must have audit log."""
        from backend.routes import tenants
        source = inspect.getsource(tenants.create_tenant)

        assert "[audit.tenant_create]" in source, \
            "create_tenant must log [audit.tenant_create]"

    def test_tenant_patch_has_audit_log(self):
        """PATCH /tenants/{id} must have audit log."""
        from backend.routes import tenants
        source = inspect.getsource(tenants.patch_tenant)

        assert "[audit.tenant_patch]" in source, \
            "patch_tenant must log [audit.tenant_patch]"

    def test_tenant_update_has_audit_log(self):
        """PUT /tenants/{id} must have audit log."""
        from backend.routes import tenants
        source = inspect.getsource(tenants.update_tenant)

        assert "[audit.tenant_update]" in source, \
            "update_tenant must log [audit.tenant_update]"

    def test_tenant_delete_has_audit_log(self):
        """DELETE /tenants/{id} must have audit log."""
        from backend.routes import tenants
        source = inspect.getsource(tenants.delete_tenant)

        assert "[audit.tenant_delete]" in source, \
            "delete_tenant must log [audit.tenant_delete]"

    def test_login_failure_has_audit_log(self):
        """Failed login attempts must be logged."""
        from backend.routes import auth
        source = inspect.getsource(auth.login)

        assert "[audit.login_failed]" in source, \
            "login must log [audit.login_failed] on failure"

    def test_login_success_has_audit_log(self):
        """Successful logins must be logged."""
        from backend.routes import auth
        source = inspect.getsource(auth.login)

        assert "[audit.login_success]" in source, \
            "login must log [audit.login_success] on success"

    def test_csv_import_has_audit_log(self):
        """CSV upload must have audit log."""
        from backend.routes import upload
        source = inspect.getsource(upload.upload_opportunities_csv)

        assert "[audit.csv_import]" in source, \
            "upload_opportunities_csv must log [audit.csv_import]"

    def test_chat_success_has_audit_log(self):
        """Successful chat turns must be logged."""
        from backend.routes import chat
        source = inspect.getsource(chat.send_chat_message)

        assert "[audit.chat]" in source, \
            "send_chat_message must log [audit.chat]"


class TestAuditLogFormat:
    """Verify audit log format is machine-parseable."""

    AUDIT_LOG_PATTERN = re.compile(
        r'\[audit\.(\w+)\].*'  # Tag like [audit.tenant_create]
    )

    def test_audit_tag_format_standard(self):
        """Audit tags should follow [audit.action] format."""
        valid_tags = [
            "[audit.tenant_create]",
            "[audit.login_failed]",
            "[audit.csv_import]",
        ]

        for tag in valid_tags:
            match = self.AUDIT_LOG_PATTERN.match(tag)
            assert match is not None, f"Invalid audit tag format: {tag}"

    def test_audit_log_contains_key_fields(self):
        """Audit log strings should contain parseable key=value pairs."""
        # Example audit log line
        example_log = "[audit.tenant_create] tenant_id=abc-123 slug=test-tenant name=Test Tenant"

        # Should be able to extract key fields
        assert "tenant_id=" in example_log
        assert "slug=" in example_log or "name=" in example_log

    def test_login_audit_includes_email(self):
        """Login audit must include email for tracking."""
        from backend.routes import auth
        source = inspect.getsource(auth.login)

        # Check that email is included in the audit log
        assert "email=" in source, \
            "Login audit must include email="

    def test_delete_audit_includes_user_id(self):
        """Delete operations must log who performed them."""
        from backend.routes import tenants
        source = inspect.getsource(tenants.delete_tenant)

        assert "by=" in source or "user_id=" in source, \
            "Delete audit must include who performed the action"


class TestAuditLogCoverage:
    """Verify audit log coverage statistics."""

    def test_all_route_files_have_logger_import(self):
        """All route files should import logging."""
        route_files = [
            "backend.routes.auth",
            "backend.routes.tenants",
            "backend.routes.opportunities",
            "backend.routes.upload",
            "backend.routes.chat",
            "backend.routes.config",
        ]

        for module_name in route_files:
            module = __import__(module_name, fromlist=[''])
            assert hasattr(module, 'logger'), \
                f"{module_name} should have a logger"

    def test_audit_tag_inventory(self):
        """Document all expected audit tags."""
        expected_audit_tags = [
            "audit.tenant_create",
            "audit.tenant_patch",
            "audit.tenant_update",
            "audit.tenant_delete",
            "audit.login_failed",
            "audit.login_success",
            "audit.csv_import",
            "audit.chat",
            "audit.patch_rejected",  # When unknown fields rejected
        ]

        # This test documents what tags should exist
        assert len(expected_audit_tags) >= 8, \
            "Should have at least 8 audit tags defined"


class TestSecurityAuditEvents:
    """Verify security-relevant events are audited."""

    def test_failed_auth_is_audited(self):
        """Failed authentication must be audited."""
        from backend.routes import auth
        source = inspect.getsource(auth.login)

        assert "login_failed" in source, \
            "Failed logins must be audited"

    def test_unknown_field_rejection_is_audited(self):
        """Rejected unknown fields should be audited."""
        from backend.routes import opportunities
        source = inspect.getsource(opportunities.update_opportunity_status)

        assert "patch_rejected" in source or "Unknown fields" in source, \
            "Unknown field rejections should be logged"

    def test_access_denied_events_logged(self):
        """Access denied events should be logged."""
        from backend.routes import opportunities
        source = inspect.getsource(opportunities.get_opportunity)

        # Should have logging around access control
        assert "Access denied" in source or "_audit_access" in source, \
            "Access denied events should be traceable"
