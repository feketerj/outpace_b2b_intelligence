"""
Invariant assertions for runtime safety checks.

These assertions verify that critical assumptions hold during execution.
Violations are logged and raised as exceptions - FAIL LOUD.

Usage:
    from backend.utils.invariants import assert_tenant_match, assert_not_empty

    # After any query returning tenant data:
    assert_tenant_match(results, expected_tenant_id)

    # Before processing critical data:
    assert_not_empty(data, "input_records")
"""

import logging
from typing import List, Optional, Any

logger = logging.getLogger(__name__)


class InvariantViolation(Exception):
    """Raised when a runtime invariant is violated."""
    pass


def assert_tenant_match(docs: List[dict], expected_tenant: str, context: str = "query") -> None:
    """
    Fail loud if any document belongs to the wrong tenant.

    CRITICAL: This catches cross-tenant data leakage at runtime.
    Call after every query that returns tenant-scoped data.

    Args:
        docs: List of documents to check
        expected_tenant: The tenant_id that all docs should belong to
        context: Description of where this check is happening (for logging)

    Raises:
        InvariantViolation: If any document has a different tenant_id
    """
    for i, doc in enumerate(docs):
        actual_tenant = doc.get("tenant_id")
        if actual_tenant is not None and actual_tenant != expected_tenant:
            logger.critical(
                f"[INVARIANT_VIOLATION] tenant_mismatch in {context}: "
                f"expected={expected_tenant} got={actual_tenant} doc_index={i}"
            )
            raise InvariantViolation(
                f"Cross-tenant data detected in {context}: "
                f"expected tenant {expected_tenant}, found {actual_tenant}"
            )


def assert_single_tenant(docs: List[dict], context: str = "query") -> None:
    """
    Fail loud if documents belong to multiple tenants.

    Use when a query should only return data from ONE tenant,
    but you don't know which tenant ahead of time.

    Args:
        docs: List of documents to check
        context: Description of where this check is happening

    Raises:
        InvariantViolation: If documents span multiple tenants
    """
    if not docs:
        return

    tenant_ids = set(doc.get("tenant_id") for doc in docs if doc.get("tenant_id"))
    if len(tenant_ids) > 1:
        logger.critical(
            f"[INVARIANT_VIOLATION] multi_tenant_result in {context}: "
            f"found tenants={tenant_ids}"
        )
        raise InvariantViolation(
            f"Query returned data from multiple tenants in {context}: {tenant_ids}"
        )


def assert_not_empty(data: Any, name: str = "data") -> None:
    """
    Fail loud if data is None, empty list, or empty dict.

    Args:
        data: The data to check
        name: Name of the data for error messages

    Raises:
        InvariantViolation: If data is empty
    """
    if data is None:
        logger.critical(f"[INVARIANT_VIOLATION] {name} is None")
        raise InvariantViolation(f"{name} is None")

    if isinstance(data, (list, dict, str)) and len(data) == 0:
        logger.critical(f"[INVARIANT_VIOLATION] {name} is empty")
        raise InvariantViolation(f"{name} is empty")


def assert_insert_succeeded(result, context: str = "insert") -> None:
    """
    Fail loud if a MongoDB insert did not return an inserted_id.

    Args:
        result: The result from insert_one()
        context: Description of what was being inserted

    Raises:
        InvariantViolation: If inserted_id is None
    """
    if result is None or getattr(result, 'inserted_id', None) is None:
        logger.critical(f"[INVARIANT_VIOLATION] insert_failed in {context}: no inserted_id")
        raise InvariantViolation(f"Insert returned no ID in {context}")


def assert_update_modified(result, context: str = "update", expected_count: int = 1) -> None:
    """
    Fail loud if a MongoDB update did not modify the expected number of documents.

    Args:
        result: The result from update_one() or update_many()
        context: Description of what was being updated
        expected_count: Expected modified_count (default 1)

    Raises:
        InvariantViolation: If modified_count doesn't match expected
    """
    modified = getattr(result, 'modified_count', 0)
    if modified != expected_count:
        logger.critical(
            f"[INVARIANT_VIOLATION] update_mismatch in {context}: "
            f"expected={expected_count} modified={modified}"
        )
        raise InvariantViolation(
            f"Update in {context}: expected {expected_count} modifications, got {modified}"
        )


def assert_auth_tenant_access(
    user_tenant_id: Optional[str],
    requested_tenant_id: str,
    user_role: str,
    context: str = "access"
) -> None:
    """
    Fail loud if tenant access is invalid (unless super_admin).

    Args:
        user_tenant_id: The tenant_id from the JWT token
        requested_tenant_id: The tenant_id being accessed
        user_role: The role from the JWT token
        context: Description of the access attempt

    Raises:
        InvariantViolation: If non-super_admin accessing wrong tenant
    """
    if user_role == "super_admin":
        return  # Super admins can access any tenant

    if user_tenant_id != requested_tenant_id:
        logger.critical(
            f"[INVARIANT_VIOLATION] unauthorized_tenant_access in {context}: "
            f"user_tenant={user_tenant_id} requested={requested_tenant_id} role={user_role}"
        )
        raise InvariantViolation(
            f"Unauthorized tenant access in {context}: "
            f"user from {user_tenant_id} attempting to access {requested_tenant_id}"
        )


def assert_field_present(doc: dict, field: str, context: str = "document") -> None:
    """
    Fail loud if a required field is missing from a document.

    Args:
        doc: The document to check
        field: The field name that must be present
        context: Description of the document

    Raises:
        InvariantViolation: If field is missing or None
    """
    if field not in doc or doc[field] is None:
        logger.critical(
            f"[INVARIANT_VIOLATION] missing_field in {context}: field={field}"
        )
        raise InvariantViolation(f"Required field '{field}' missing in {context}")


def assert_fields_present(doc: dict, fields: List[str], context: str = "document") -> None:
    """
    Fail loud if any required fields are missing.

    Args:
        doc: The document to check
        fields: List of field names that must be present
        context: Description of the document

    Raises:
        InvariantViolation: If any field is missing or None
    """
    missing = [f for f in fields if f not in doc or doc[f] is None]
    if missing:
        logger.critical(
            f"[INVARIANT_VIOLATION] missing_fields in {context}: fields={missing}"
        )
        raise InvariantViolation(f"Required fields {missing} missing in {context}")
