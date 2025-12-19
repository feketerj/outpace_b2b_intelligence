#!/usr/bin/env python3
"""
DELIVERABLE A: Sync Contract Schema Validator
=============================================
Strict schema validator for sync endpoint responses.

NON-NEGOTIABLE RULES:
- All 7 fields required: tenant_id, tenant_name, opportunities_synced,
  intelligence_synced, status, sync_timestamp, errors
- tenant_id must be valid UUID (strict)
- status must be 'success' or 'partial'
- If status=partial, errors MUST be non-empty
- If status=success, errors MUST be empty
- sync_timestamp must be ISO parseable
- counts must be non-negative integers

Any violation is a HARD FAILURE.
"""
import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class SyncStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"


# Strict UUID regex (RFC 4122)
UUID_REGEX = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# Relaxed UUID regex for legacy compatibility
UUID_REGEX_RELAXED = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


@dataclass
class ValidationResult:
    """Result of contract validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    parsed_data: Optional[Dict[str, Any]] = None
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __str__(self) -> str:
        if self.valid:
            return f"VALID (warnings: {len(self.warnings)})"
        return f"INVALID: {'; '.join(self.errors)}"


class SyncContractValidator:
    """
    Strict validator for sync endpoint response contract.
    
    Usage:
        validator = SyncContractValidator()
        result = validator.validate(response_dict)
        if not result:
            raise ContractViolation(result.errors)
    
    P0 HARDENING: Strict RFC 4122 UUID validation is NOW DEFAULT.
    Relaxed mode requires explicit opt-in AND is logged as a warning.
    """
    
    REQUIRED_FIELDS = {
        'tenant_id': str,
        'tenant_name': str,
        'opportunities_synced': int,
        'intelligence_synced': int,
        'status': str,
        'sync_timestamp': str,
        'errors': list,
    }
    
    def __init__(self, strict_uuid: bool = True, allow_relaxed_uuid: bool = False):
        """
        Args:
            strict_uuid: If True (DEFAULT), use RFC 4122 strict UUID validation.
                        If False, requires allow_relaxed_uuid=True or raises.
            allow_relaxed_uuid: Must be explicitly True to use relaxed UUID mode.
                               This is a P0 safety gate.
        """
        # P0 HARDENING: Strict UUID is default. Relaxed requires explicit opt-in.
        if not strict_uuid and not allow_relaxed_uuid:
            raise ValueError(
                "Relaxed UUID validation requires explicit allow_relaxed_uuid=True. "
                "This is a P0 safety gate. Strict RFC 4122 UUIDs are required by default."
            )
        
        self.strict_uuid = strict_uuid
        self.allow_relaxed_uuid = allow_relaxed_uuid
        self.uuid_regex = UUID_REGEX if strict_uuid else UUID_REGEX_RELAXED
        
        if not strict_uuid:
            import warnings
            warnings.warn(
                "SyncContractValidator using RELAXED UUID validation. "
                "This weakens P0 guarantees and should only be used for legacy compatibility.",
                UserWarning
            )
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Validate sync response against contract.
        
        Returns ValidationResult with valid=False on ANY violation.
        """
        errors = []
        warnings = []
        
        # Check for regression pattern (old async response)
        if 'message' in data:
            msg = str(data.get('message', '')).lower()
            if 'triggered' in msg:
                errors.append(
                    f"REGRESSION_DETECTED: Old async message pattern found: '{data['message']}'"
                )
                return ValidationResult(False, errors, warnings)
        
        # Check all required fields exist
        missing = [f for f in self.REQUIRED_FIELDS if f not in data]
        if missing:
            errors.append(f"MISSING_FIELDS: {missing}")
            return ValidationResult(False, errors, warnings)
        
        # Validate types
        for field, expected_type in self.REQUIRED_FIELDS.items():
            actual = data[field]
            if not isinstance(actual, expected_type):
                errors.append(
                    f"TYPE_ERROR: {field} expected {expected_type.__name__}, "
                    f"got {type(actual).__name__}"
                )
        
        if errors:
            return ValidationResult(False, errors, warnings)
        
        # Validate tenant_id UUID format
        tenant_id = data['tenant_id']
        if not self.uuid_regex.match(tenant_id):
            errors.append(f"INVALID_UUID: tenant_id '{tenant_id}' is not valid UUID format")
        
        # Validate status enum
        status = data['status']
        valid_statuses = [s.value for s in SyncStatus]
        if status not in valid_statuses:
            errors.append(f"INVALID_STATUS: '{status}' not in {valid_statuses}")
        
        # Validate sync_timestamp is parseable ISO
        sync_ts = data['sync_timestamp']
        parsed_ts = self._parse_timestamp(sync_ts)
        if parsed_ts is None:
            errors.append(f"UNPARSEABLE_TIMESTAMP: '{sync_ts}' is not valid ISO format")
        
        # Validate counts are non-negative
        for count_field in ['opportunities_synced', 'intelligence_synced']:
            if data[count_field] < 0:
                errors.append(f"NEGATIVE_COUNT: {count_field}={data[count_field]}")
        
        # Validate errors list type contents
        errors_list = data['errors']
        for i, err in enumerate(errors_list):
            if not isinstance(err, str):
                warnings.append(f"errors[{i}] is not string: {type(err).__name__}")
        
        # CRITICAL: Conditional validation based on status
        if status == SyncStatus.PARTIAL.value:
            if len(errors_list) == 0:
                errors.append(
                    "CONTRACT_VIOLATION: status='partial' but errors list is empty. "
                    "Partial status MUST have non-empty errors."
                )
        elif status == SyncStatus.SUCCESS.value:
            if len(errors_list) > 0:
                errors.append(
                    f"CONTRACT_VIOLATION: status='success' but errors list has "
                    f"{len(errors_list)} items. Success status MUST have empty errors."
                )
        
        if errors:
            return ValidationResult(False, errors, warnings)
        
        return ValidationResult(
            valid=True,
            errors=[],
            warnings=warnings,
            parsed_data={
                'tenant_id': tenant_id,
                'tenant_name': data['tenant_name'],
                'opportunities_synced': data['opportunities_synced'],
                'intelligence_synced': data['intelligence_synced'],
                'status': status,
                'sync_timestamp': sync_ts,
                'sync_timestamp_parsed': parsed_ts,
                'errors': errors_list,
            }
        )
    
    def _parse_timestamp(self, ts: str) -> Optional[datetime]:
        """Parse ISO timestamp, handling various formats."""
        try:
            # Handle Z suffix
            ts_clean = ts.replace('Z', '+00:00')
            return datetime.fromisoformat(ts_clean)
        except (ValueError, TypeError):
            return None
    
    def validate_json(self, json_str: str) -> ValidationResult:
        """Validate from JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                errors=[f"JSON_PARSE_ERROR: {e}"],
                warnings=[]
            )
        return self.validate(data)


# Singleton for convenience
_default_validator = SyncContractValidator(strict_uuid=False)


def validate_sync_contract(data: Dict[str, Any]) -> ValidationResult:
    """Convenience function using default validator."""
    return _default_validator.validate(data)


def validate_sync_contract_strict(data: Dict[str, Any]) -> ValidationResult:
    """Convenience function using strict UUID validation."""
    return SyncContractValidator(strict_uuid=True).validate(data)


if __name__ == "__main__":
    # Self-test
    test_valid = {
        "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21",
        "tenant_name": "Test Tenant",
        "opportunities_synced": 10,
        "intelligence_synced": 0,
        "status": "success",
        "sync_timestamp": "2025-01-01T00:00:00+00:00",
        "errors": []
    }
    
    result = validate_sync_contract(test_valid)
    print(f"Valid contract: {result}")
    assert result.valid, f"Should be valid: {result.errors}"
    
    test_invalid = {
        "status": "success",
        "message": "Sync triggered successfully"
    }
    result = validate_sync_contract(test_invalid)
    print(f"Invalid contract: {result}")
    assert not result.valid, "Should detect regression"
    
    print("\n✅ Self-test passed")
