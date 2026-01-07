#!/usr/bin/env python3
"""
DELIVERABLE C: SYNC-02 Test Harness Guardrails (P0 HARDENED)
============================================================
Enforces single sync call constraint and prevents unauthorized sync attempts.

P0 HARDENING ADDITIONS:
- Global network deny by default in CI
- Runtime enforcement (not convention-based)
- Explicit allowlist for SYNC-02 context only

GUARDRAILS:
1. SYNC-02 can only run ONCE per test session
2. No other test can make real sync calls
3. Sync calls must block until completion
4. Marker written atomically only on success
5. On failure, no marker written
6. ALL network calls blocked outside SYNC-02 context (P0)

Usage in tests:
    from guardrails.sync_guardrails import SyncGuard, sync_guard, network_deny_guard
    
    # Decorator approach
    @sync_guard.protected
    def test_sync_endpoint():
        pass  # This test cannot make sync calls
    
    # Context manager approach
    with sync_guard.allow_sync():
        # Only here can SYNC-02 run AND network is allowed
        pass
    
    # Network deny is AUTOMATIC in CI mode
"""
import os
import sys
import json
import threading
import functools
import tempfile
import socket
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch


class SyncGuardViolation(Exception):
    """Raised when sync guardrails are violated."""
    pass


class NetworkDenyViolation(Exception):
    """Raised when unauthorized network access is attempted in CI."""
    pass


class NetworkDenyGuard:
    """
    P0 HARDENING: Global network deny outside SYNC-02 context.
    
    In CI mode (CI=true env var), ALL socket connections are blocked
    by default. Network access is ONLY allowed within sync_guard.allow_sync().
    
    This is RUNTIME enforcement, not convention-based.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._network_allowed = False
        self._original_socket_connect = None
        self._is_ci = os.environ.get('CI', '').lower() in ('true', '1', 'yes')
        self._is_pr_mode = os.environ.get('PR_MODE', '').lower() in ('true', '1', 'yes')
        self._deny_active = False
        self._network_lock = threading.Lock()
        self._initialized = True
    
    def _blocked_connect(self, *args, **kwargs):
        """Replacement socket.connect that blocks unauthorized connections."""
        if not self._network_allowed:
            raise NetworkDenyViolation(
                "NETWORK ACCESS DENIED: Attempted socket connection outside SYNC-02 context. "
                "In CI mode, all network calls are blocked except within sync_guard.allow_sync(). "
                "This is a P0 guardrail violation."
            )
        return self._original_socket_connect(*args, **kwargs)
    
    def activate(self):
        """Activate global network deny (called at test session start in CI)."""
        if not self._is_ci:
            return  # Only enforce in CI
        
        with self._network_lock:
            if self._deny_active:
                return
            
            self._original_socket_connect = socket.socket.connect
            socket.socket.connect = lambda self_sock, *args, **kwargs: \
                network_deny_guard._blocked_connect_wrapper(self_sock, *args, **kwargs)
            self._deny_active = True
    
    def _blocked_connect_wrapper(self, sock, *args, **kwargs):
        """Wrapper that checks network allowance."""
        if not self._network_allowed:
            raise NetworkDenyViolation(
                f"NETWORK ACCESS DENIED: Attempted connection to {args[0] if args else 'unknown'}. "
                "Network calls blocked outside SYNC-02 context in CI mode."
            )
        return self._original_socket_connect(sock, *args, **kwargs)
    
    def deactivate(self):
        """Deactivate global network deny (called at test session end)."""
        with self._network_lock:
            if not self._deny_active:
                return
            
            if self._original_socket_connect:
                socket.socket.connect = self._original_socket_connect
                self._original_socket_connect = None
            self._deny_active = False
    
    @contextmanager
    def allow_network(self):
        """Context manager to temporarily allow network access (SYNC-02 only)."""
        with self._network_lock:
            was_allowed = self._network_allowed
            self._network_allowed = True
        try:
            yield
        finally:
            with self._network_lock:
                self._network_allowed = was_allowed
    
    @property
    def is_active(self) -> bool:
        return self._deny_active
    
    @property
    def is_network_allowed(self) -> bool:
        return self._network_allowed


# Singleton instance
network_deny_guard = NetworkDenyGuard()


class SyncGuard:
    """
    Singleton guard that enforces sync call constraints.
    
    NON-NEGOTIABLE RULES:
    - Only ONE sync call allowed per test session
    - Sync calls outside allowed context raise SyncGuardViolation
    - Marker file written atomically only on contract validation pass
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._sync_count = 0
        self._sync_allowed = False
        self._max_sync_calls = 1
        self._sync_lock = threading.Lock()
        self._marker_path = "/tmp/carfax_sync02_ok.marker"
        self._initialized = True
    
    def reset(self):
        """Reset guard state (for testing the guard itself)."""
        with self._sync_lock:
            self._sync_count = 0
            self._sync_allowed = False
    
    @contextmanager
    def allow_sync(self):
        """
        Context manager that allows a sync call AND network access.
        
        P0 HARDENED: This is the ONLY place where network is allowed in CI.
        
        Usage:
            with sync_guard.allow_sync():
                # Make sync call here - network is allowed
                pass
        
        Raises:
            SyncGuardViolation: If sync has already been called
        """
        with self._sync_lock:
            if self._sync_count >= self._max_sync_calls:
                raise SyncGuardViolation(
                    f"SYNC-02 already executed {self._sync_count} time(s). "
                    f"Only {self._max_sync_calls} sync call(s) allowed per session."
                )
            self._sync_allowed = True
        
        # P0 HARDENING: Enable network access within sync context
        try:
            with network_deny_guard.allow_network():
                yield self
        finally:
            with self._sync_lock:
                self._sync_allowed = False
    
    def register_sync_call(self):
        """
        Register that a sync call is about to be made.
        
        Raises:
            SyncGuardViolation: If sync is not allowed or limit exceeded
        """
        with self._sync_lock:
            if not self._sync_allowed:
                raise SyncGuardViolation(
                    "Sync call attempted outside allowed context. "
                    "Use 'with sync_guard.allow_sync():' to enable."
                )
            
            if self._sync_count >= self._max_sync_calls:
                raise SyncGuardViolation(
                    f"Sync limit exceeded: {self._sync_count}/{self._max_sync_calls}"
                )
            
            self._sync_count += 1
    
    def protected(self, func: Callable) -> Callable:
        """
        Decorator that marks a test as protected from making sync calls.
        
        Usage:
            @sync_guard.protected
            def test_something():
                pass  # Cannot make sync calls here
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Temporarily ensure sync is not allowed
            original_allowed = self._sync_allowed
            self._sync_allowed = False
            try:
                return func(*args, **kwargs)
            finally:
                self._sync_allowed = original_allowed
        return wrapper
    
    def write_marker_atomic(
        self, 
        sync_response: Dict[str, Any],
        marker_path: Optional[str] = None
    ) -> bool:
        """
        Write marker file atomically (temp + mv).
        
        Only writes if sync_response contains valid contract fields.
        
        Returns:
            True if marker written successfully
            False if validation failed (no marker written)
        """
        from backend.tests.validators.sync_contract_validator import validate_sync_contract
        
        path = marker_path or self._marker_path
        
        # Validate contract first
        result = validate_sync_contract(sync_response)
        if not result:
            # Contract invalid - do NOT write marker
            return False
        
        # Build marker data
        marker_data = {
            'tenant_id': sync_response.get('tenant_id'),
            'status': sync_response.get('status'),
            'sync_timestamp': sync_response.get('sync_timestamp'),
            'opportunities_synced': sync_response.get('opportunities_synced'),
            'intelligence_synced': sync_response.get('intelligence_synced'),
            'contract_validated': True,
            'marker_created_utc': datetime.now(timezone.utc).isoformat(),
        }
        
        # Atomic write: temp file + rename
        temp_path = f"{path}.tmp.{os.getpid()}"
        try:
            with open(temp_path, 'w') as f:
                json.dump(marker_data, f)
            os.rename(temp_path, path)
            return True
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def delete_marker(self, marker_path: Optional[str] = None):
        """Delete marker file (for test setup)."""
        path = marker_path or self._marker_path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    
    @property
    def sync_count(self) -> int:
        """Number of sync calls made this session."""
        return self._sync_count
    
    @property
    def sync_remaining(self) -> int:
        """Number of sync calls remaining."""
        return max(0, self._max_sync_calls - self._sync_count)


# Singleton instance
sync_guard = SyncGuard()


# Convenience functions
def assert_no_sync_calls():
    """Assert that no sync calls have been made."""
    if sync_guard.sync_count > 0:
        raise SyncGuardViolation(
            f"Expected no sync calls, but {sync_guard.sync_count} were made"
        )


def assert_single_sync_call():
    """Assert that exactly one sync call was made."""
    if sync_guard.sync_count != 1:
        raise SyncGuardViolation(
            f"Expected exactly 1 sync call, but {sync_guard.sync_count} were made"
        )
