"""
Guardrails package for sync test constraints.

P0 HARDENED:
- Strict single sync call enforcement
- Global network deny outside SYNC-02 context
- Runtime enforcement (not convention-based)
"""
from .sync_guardrails import (
    SyncGuard,
    SyncGuardViolation,
    NetworkDenyGuard,
    NetworkDenyViolation,
    sync_guard,
    network_deny_guard,
    assert_no_sync_calls,
    assert_single_sync_call,
)

__all__ = [
    'SyncGuard',
    'SyncGuardViolation',
    'NetworkDenyGuard',
    'NetworkDenyViolation',
    'sync_guard',
    'network_deny_guard',
    'assert_no_sync_calls',
    'assert_single_sync_call',
]
