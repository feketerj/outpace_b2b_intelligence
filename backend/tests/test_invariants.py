"""
Invariant Guards - Test runtime invariant assertions.

These tests verify that:
1. Invariant violations are detected and raised
2. Invariant helpers work correctly
3. All critical invariants have tests

Run: pytest backend/tests/test_invariants.py -v
"""

import pytest
from backend.utils.invariants import (
    InvariantViolation,
    assert_tenant_match,
    assert_single_tenant,
    assert_not_empty,
    assert_insert_succeeded,
    assert_update_modified,
    assert_auth_tenant_access,
    assert_field_present,
    assert_fields_present,
)


class TestInvariantViolationException:
    """Test the InvariantViolation exception."""

    def test_invariant_violation_is_exception(self):
        """InvariantViolation should be a proper exception."""
        assert issubclass(InvariantViolation, Exception)

    def test_invariant_violation_has_message(self):
        """InvariantViolation should preserve message."""
        error = InvariantViolation("Test message")
        assert str(error) == "Test message"


class TestAssertTenantMatch:
    """Test tenant matching invariant."""

    def test_passes_for_matching_tenants(self):
        """All docs with correct tenant_id should pass."""
        docs = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-a"},
        ]
        assert_tenant_match(docs, "tenant-a")  # Should not raise

    def test_passes_for_empty_list(self):
        """Empty list should pass."""
        assert_tenant_match([], "tenant-a")  # Should not raise

    def test_fails_for_mismatched_tenant(self):
        """Doc with wrong tenant_id should fail."""
        docs = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-b"},  # Wrong!
        ]
        with pytest.raises(InvariantViolation) as exc_info:
            assert_tenant_match(docs, "tenant-a")

        assert "Cross-tenant" in str(exc_info.value)

    def test_passes_for_none_tenant_id(self):
        """Docs without tenant_id (None) should pass."""
        docs = [
            {"id": "1", "tenant_id": None},
            {"id": "2"},  # No tenant_id key
        ]
        assert_tenant_match(docs, "tenant-a")  # Should not raise


class TestAssertSingleTenant:
    """Test single tenant invariant."""

    def test_passes_for_single_tenant(self):
        """Docs all from one tenant should pass."""
        docs = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-a"},
        ]
        assert_single_tenant(docs)  # Should not raise

    def test_fails_for_multiple_tenants(self):
        """Docs from multiple tenants should fail."""
        docs = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-b"},
        ]
        with pytest.raises(InvariantViolation) as exc_info:
            assert_single_tenant(docs)

        assert "multiple tenants" in str(exc_info.value)

    def test_passes_for_empty_list(self):
        """Empty list should pass."""
        assert_single_tenant([])  # Should not raise


class TestAssertNotEmpty:
    """Test not-empty invariant."""

    def test_passes_for_non_empty_list(self):
        """Non-empty list should pass."""
        assert_not_empty([1, 2, 3], "items")

    def test_passes_for_non_empty_dict(self):
        """Non-empty dict should pass."""
        assert_not_empty({"key": "value"}, "config")

    def test_passes_for_non_empty_string(self):
        """Non-empty string should pass."""
        assert_not_empty("hello", "message")

    def test_fails_for_none(self):
        """None should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_not_empty(None, "data")

        assert "data is None" in str(exc_info.value)

    def test_fails_for_empty_list(self):
        """Empty list should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_not_empty([], "items")

        assert "items is empty" in str(exc_info.value)

    def test_fails_for_empty_dict(self):
        """Empty dict should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_not_empty({}, "config")

        assert "config is empty" in str(exc_info.value)

    def test_fails_for_empty_string(self):
        """Empty string should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_not_empty("", "message")

        assert "message is empty" in str(exc_info.value)


class TestAssertInsertSucceeded:
    """Test insert success invariant."""

    def test_passes_for_valid_result(self):
        """Result with inserted_id should pass."""
        class MockResult:
            inserted_id = "abc123"

        assert_insert_succeeded(MockResult(), "test_insert")

    def test_fails_for_none_result(self):
        """None result should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_insert_succeeded(None, "test_insert")

        assert "Insert returned no ID" in str(exc_info.value)

    def test_fails_for_none_inserted_id(self):
        """Result with None inserted_id should fail."""
        class MockResult:
            inserted_id = None

        with pytest.raises(InvariantViolation) as exc_info:
            assert_insert_succeeded(MockResult(), "test_insert")

        assert "Insert returned no ID" in str(exc_info.value)


class TestAssertUpdateModified:
    """Test update modified count invariant."""

    def test_passes_for_expected_count(self):
        """Result with expected modified_count should pass."""
        class MockResult:
            modified_count = 1

        assert_update_modified(MockResult(), "test_update", expected_count=1)

    def test_fails_for_wrong_count(self):
        """Result with wrong modified_count should fail."""
        class MockResult:
            modified_count = 0

        with pytest.raises(InvariantViolation) as exc_info:
            assert_update_modified(MockResult(), "test_update", expected_count=1)

        assert "expected 1 modifications, got 0" in str(exc_info.value)


class TestAssertAuthTenantAccess:
    """Test auth tenant access invariant."""

    def test_passes_for_same_tenant(self):
        """User accessing own tenant should pass."""
        assert_auth_tenant_access("tenant-a", "tenant-a", "tenant_user", "test")

    def test_passes_for_super_admin(self):
        """Super admin accessing any tenant should pass."""
        assert_auth_tenant_access("tenant-a", "tenant-b", "super_admin", "test")

    def test_fails_for_cross_tenant_access(self):
        """Non-super-admin cross-tenant access should fail."""
        with pytest.raises(InvariantViolation) as exc_info:
            assert_auth_tenant_access("tenant-a", "tenant-b", "tenant_user", "test")

        assert "Unauthorized tenant access" in str(exc_info.value)


class TestAssertFieldPresent:
    """Test field presence invariant."""

    def test_passes_when_field_exists(self):
        """Field that exists should pass."""
        doc = {"id": "123", "name": "Test"}
        assert_field_present(doc, "id", "test_doc")

    def test_fails_when_field_missing(self):
        """Missing field should fail."""
        doc = {"id": "123"}
        with pytest.raises(InvariantViolation) as exc_info:
            assert_field_present(doc, "name", "test_doc")

        assert "Required field 'name' missing" in str(exc_info.value)

    def test_fails_when_field_is_none(self):
        """Field with None value should fail."""
        doc = {"id": "123", "name": None}
        with pytest.raises(InvariantViolation) as exc_info:
            assert_field_present(doc, "name", "test_doc")

        assert "Required field 'name' missing" in str(exc_info.value)


class TestAssertFieldsPresent:
    """Test multiple fields presence invariant."""

    def test_passes_when_all_fields_exist(self):
        """All required fields present should pass."""
        doc = {"id": "123", "name": "Test", "status": "active"}
        assert_fields_present(doc, ["id", "name", "status"], "test_doc")

    def test_fails_when_any_field_missing(self):
        """Any missing field should fail."""
        doc = {"id": "123", "name": "Test"}
        with pytest.raises(InvariantViolation) as exc_info:
            assert_fields_present(doc, ["id", "name", "status"], "test_doc")

        assert "status" in str(exc_info.value)

    def test_lists_all_missing_fields(self):
        """Should list all missing fields."""
        doc = {"id": "123"}
        with pytest.raises(InvariantViolation) as exc_info:
            assert_fields_present(doc, ["id", "name", "status", "type"], "test_doc")

        error_msg = str(exc_info.value)
        assert "name" in error_msg
        assert "status" in error_msg
        assert "type" in error_msg
