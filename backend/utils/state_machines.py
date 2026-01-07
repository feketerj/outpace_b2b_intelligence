"""
State machine validators for status transitions.

These ensure that entity status changes follow valid paths.
Invalid transitions fail loud with HTTP 400.

Usage:
    from backend.utils.state_machines import validate_tenant_status_transition

    validate_tenant_status_transition(current_status, new_status)
"""

import logging
from typing import Dict, Set
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class InvalidStateTransition(Exception):
    """Raised when a state transition is not allowed."""
    pass


# ==================== TENANT STATUS TRANSITIONS ====================

TENANT_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    "ACTIVE": {"SUSPENDED", "INACTIVE"},
    "SUSPENDED": {"ACTIVE", "INACTIVE"},
    "INACTIVE": {"ACTIVE"},  # Reactivation only - cannot go to SUSPENDED directly
}


def validate_tenant_status_transition(current: str, new: str) -> None:
    """
    Validate that a tenant status transition is allowed.

    Valid transitions:
        ACTIVE -> SUSPENDED (valid)
        ACTIVE -> INACTIVE (valid)
        SUSPENDED -> ACTIVE (valid)
        SUSPENDED -> INACTIVE (valid)
        INACTIVE -> ACTIVE (valid - reactivation)
        INACTIVE -> SUSPENDED (INVALID - must activate first)

    Args:
        current: Current status value
        new: Proposed new status value

    Raises:
        HTTPException 400: If transition is not allowed
    """
    if current == new:
        return  # No-op transitions are always valid

    current_upper = current.upper() if current else ""
    new_upper = new.upper() if new else ""

    allowed = TENANT_STATUS_TRANSITIONS.get(current_upper, set())

    if new_upper not in allowed:
        logger.warning(
            f"[state_machine.tenant] INVALID_TRANSITION: {current} -> {new}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {current} -> {new}. "
                   f"Allowed from {current}: {list(allowed) if allowed else 'none'}"
        )


# ==================== DOCUMENT STATUS TRANSITIONS (RAG) ====================

DOCUMENT_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    "pending": {"processing"},
    "processing": {"ready", "failed"},
    "ready": set(),  # Immutable once ready
    "failed": {"processing"},  # Can retry
}


def validate_document_status_transition(current: str, new: str) -> None:
    """
    Validate that a document status transition is allowed.

    Valid transitions:
        pending -> processing (valid)
        processing -> ready (valid)
        processing -> failed (valid)
        ready -> anything (INVALID - immutable once ready)
        failed -> processing (valid - retry)

    Args:
        current: Current status value
        new: Proposed new status value

    Raises:
        HTTPException 400: If transition is not allowed
    """
    if current == new:
        return

    allowed = DOCUMENT_STATUS_TRANSITIONS.get(current, set())

    if new not in allowed:
        logger.warning(
            f"[state_machine.document] INVALID_TRANSITION: {current} -> {new}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document status transition: {current} -> {new}. "
                   f"Allowed from {current}: {list(allowed) if allowed else 'none'}"
        )


# ==================== OPPORTUNITY CLIENT STATUS TRANSITIONS ====================

OPPORTUNITY_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    "new": {"reviewing", "pursuing", "not_interested", "archived"},
    "reviewing": {"pursuing", "not_interested", "archived", "new"},
    "pursuing": {"won", "lost", "archived", "reviewing"},
    "not_interested": {"reviewing", "archived"},
    "won": {"archived"},
    "lost": {"archived", "reviewing"},  # Can re-open lost opportunities
    "archived": {"new", "reviewing"},  # Can un-archive
}


def validate_opportunity_status_transition(current: str, new: str) -> None:
    """
    Validate that an opportunity client status transition is allowed.

    Args:
        current: Current client_status value
        new: Proposed new client_status value

    Raises:
        HTTPException 400: If transition is not allowed
    """
    if current == new:
        return

    # Default to "new" if current is None or empty
    current = current or "new"

    allowed = OPPORTUNITY_STATUS_TRANSITIONS.get(current, set())

    if new not in allowed:
        logger.warning(
            f"[state_machine.opportunity] INVALID_TRANSITION: {current} -> {new}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid opportunity status transition: {current} -> {new}. "
                   f"Allowed from {current}: {list(allowed) if allowed else 'none'}"
        )


# ==================== GENERIC TRANSITION VALIDATOR ====================

def validate_transition(
    current: str,
    new: str,
    transitions: Dict[str, Set[str]],
    entity_type: str = "entity"
) -> None:
    """
    Generic state transition validator.

    Args:
        current: Current state value
        new: Proposed new state value
        transitions: Dict mapping states to allowed next states
        entity_type: Name of entity for error messages

    Raises:
        HTTPException 400: If transition is not allowed
    """
    if current == new:
        return

    allowed = transitions.get(current, set())

    if new not in allowed:
        logger.warning(
            f"[state_machine.{entity_type}] INVALID_TRANSITION: {current} -> {new}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {entity_type} transition: {current} -> {new}. "
                   f"Allowed: {list(allowed) if allowed else 'none'}"
        )
