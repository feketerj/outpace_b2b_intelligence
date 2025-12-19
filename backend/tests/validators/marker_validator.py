#!/usr/bin/env python3
"""
DELIVERABLE B: Marker File Validator
====================================
Strict validator for /tmp/carfax_sync02_ok.marker

RULES:
- File must exist
- JSON must parse
- Required fields: tenant_id, status, sync_timestamp, opportunities_synced,
  intelligence_synced, contract_validated, marker_created_utc
- contract_validated must be True (boolean)
- marker_created_utc must be <= 10 minutes old (UTC)
- tenant_id must be valid UUID
- status must be 'success' or 'partial'
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MARKER_PATH = "/tmp/carfax_sync02_ok.marker"
MAX_AGE_MINUTES = 10

UUID_REGEX = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


@dataclass
class MarkerValidationResult:
    """Result of marker file validation."""
    valid: bool
    errors: List[str]
    marker_data: Optional[Dict[str, Any]] = None
    age_seconds: Optional[float] = None
    
    def __bool__(self) -> bool:
        return self.valid
    
    def __str__(self) -> str:
        if self.valid:
            return f"VALID (age={self.age_seconds:.0f}s)"
        return f"INVALID: {'; '.join(self.errors)}"


class MarkerValidator:
    """
    Validates the SYNC-02 marker file for CI gate.
    
    The marker file is written atomically by CARFAX only when SYNC-02
    passes full contract validation. This validator ensures the marker
    is fresh, well-formed, and contains valid data.
    """
    
    REQUIRED_FIELDS = [
        'tenant_id',
        'status', 
        'sync_timestamp',
        'opportunities_synced',
        'intelligence_synced',
        'contract_validated',
        'marker_created_utc',
    ]
    
    def __init__(
        self, 
        marker_path: str = DEFAULT_MARKER_PATH,
        max_age_minutes: int = MAX_AGE_MINUTES
    ):
        self.marker_path = Path(marker_path)
        self.max_age = timedelta(minutes=max_age_minutes)
    
    def validate(self) -> MarkerValidationResult:
        """Perform full marker validation."""
        errors = []
        marker_data = None
        age_seconds = None
        
        # Check file exists
        if not self.marker_path.exists():
            errors.append(f"MARKER_NOT_FOUND: {self.marker_path}")
            return MarkerValidationResult(False, errors)
        
        # Read and parse JSON
        try:
            content = self.marker_path.read_text()
            marker_data = json.loads(content)
        except json.JSONDecodeError as e:
            errors.append(f"JSON_PARSE_ERROR: {e}")
            return MarkerValidationResult(False, errors)
        except IOError as e:
            errors.append(f"FILE_READ_ERROR: {e}")
            return MarkerValidationResult(False, errors)
        
        # Check required fields
        missing = [f for f in self.REQUIRED_FIELDS if f not in marker_data]
        if missing:
            errors.append(f"MISSING_FIELDS: {missing}")
        
        if errors:
            return MarkerValidationResult(False, errors, marker_data)
        
        # Validate contract_validated is True
        if marker_data.get('contract_validated') is not True:
            errors.append(
                f"CONTRACT_NOT_VALIDATED: contract_validated="
                f"{marker_data.get('contract_validated')}"
            )
        
        # Validate status enum
        status = marker_data.get('status')
        if status not in ['success', 'partial']:
            errors.append(f"INVALID_STATUS: '{status}' not in ['success', 'partial']")
        
        # Validate tenant_id UUID format
        tenant_id = marker_data.get('tenant_id', '')
        if not UUID_REGEX.match(str(tenant_id)):
            errors.append(f"INVALID_TENANT_ID: '{tenant_id}' is not valid UUID")
        
        # Validate and check freshness of marker_created_utc
        marker_ts = marker_data.get('marker_created_utc', '')
        parsed_ts = self._parse_timestamp(marker_ts)
        
        if parsed_ts is None:
            errors.append(f"UNPARSEABLE_TIMESTAMP: marker_created_utc='{marker_ts}'")
        else:
            now_utc = datetime.now(timezone.utc)
            if parsed_ts.tzinfo is None:
                parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
            
            age = now_utc - parsed_ts
            age_seconds = age.total_seconds()
            
            if age > self.max_age:
                errors.append(
                    f"STALE_MARKER: age={age_seconds:.0f}s, "
                    f"max={self.max_age.total_seconds():.0f}s"
                )
            elif age < timedelta(seconds=-60):  # Allow 1 min clock skew
                errors.append(f"FUTURE_TIMESTAMP: age={age_seconds:.0f}s")
        
        # Validate count types
        for count_field in ['opportunities_synced', 'intelligence_synced']:
            val = marker_data.get(count_field)
            if not isinstance(val, int):
                errors.append(f"INVALID_TYPE: {count_field} is not int")
        
        if errors:
            return MarkerValidationResult(False, errors, marker_data, age_seconds)
        
        return MarkerValidationResult(
            valid=True,
            errors=[],
            marker_data=marker_data,
            age_seconds=age_seconds
        )
    
    def _parse_timestamp(self, ts: str) -> Optional[datetime]:
        """Parse ISO timestamp."""
        try:
            ts_clean = str(ts).replace('Z', '+00:00')
            return datetime.fromisoformat(ts_clean)
        except (ValueError, TypeError):
            return None


def validate_marker(path: str = DEFAULT_MARKER_PATH) -> MarkerValidationResult:
    """Convenience function."""
    return MarkerValidator(path).validate()


if __name__ == "__main__":
    result = validate_marker()
    print(f"Marker validation: {result}")
    if result.marker_data:
        print(f"Marker data: {json.dumps(result.marker_data, indent=2)}")
