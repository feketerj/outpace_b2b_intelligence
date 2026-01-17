"""
Pytest configuration for adversarial verification harness.

P0 HARDENING:
- Explicit markers for SYNC-02 tests
- Automatic network deny in CI mode
- PR mode enforcement via markers
"""
import os
import pytest

# Guardrails module is optional - only used in CI mode
try:
    from tests.guardrails import sync_guard, network_deny_guard
    HAS_GUARDRAILS = True
except ImportError:
    HAS_GUARDRAILS = False
    sync_guard = None
    network_deny_guard = None


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "sync02: marks test as SYNC-02 (requires real network, excluded in PR mode)"
    )
    config.addinivalue_line(
        "markers", "requires_network: marks test as requiring network access"
    )
    config.addinivalue_line(
        "markers", "asyncio: marks test as async"
    )
    config.addinivalue_line(
        "markers", "external_sync: marks test as requiring external sync service (auto-skipped locally)"
    )


def pytest_collection_modifyitems(config, items):
    """
    P0 HARDENING: Automatically skip external/network tests in local mode.

    PR mode is determined by:
    - PR_MODE=true environment variable
    - --pr-mode command line flag

    External sync tests are ALWAYS skipped unless EXTERNAL_SYNC_TESTS=true.
    """
    pr_mode = (
        os.environ.get('PR_MODE', '').lower() in ('true', '1', 'yes') or
        config.getoption("--pr-mode", default=False)
    )

    # External sync tests require explicit opt-in
    run_external = os.environ.get('EXTERNAL_SYNC_TESTS', '').lower() in ('true', '1', 'yes')

    skip_sync02 = pytest.mark.skip(reason="SYNC-02 tests excluded in PR mode")
    skip_network = pytest.mark.skip(reason="Network tests excluded in PR mode")
    skip_external = pytest.mark.skip(reason="External sync tests require EXTERNAL_SYNC_TESTS=true")

    for item in items:
        # Always skip external_sync unless explicitly enabled
        if "external_sync" in item.keywords and not run_external:
            item.add_marker(skip_external)

        if pr_mode:
            if "sync02" in item.keywords:
                item.add_marker(skip_sync02)
            if "requires_network" in item.keywords:
                item.add_marker(skip_network)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--pr-mode",
        action="store_true",
        default=False,
        help="Run in PR mode (exclude SYNC-02 and network tests)"
    )


@pytest.fixture(scope="session", autouse=True)
def activate_network_deny():
    """
    P0 HARDENING: Activate global network deny at session start.

    In CI mode, ALL network calls are blocked except within sync_guard.allow_sync().
    """
    is_ci = os.environ.get('CI', '').lower() in ('true', '1', 'yes')

    if is_ci and HAS_GUARDRAILS and network_deny_guard:
        network_deny_guard.activate()

    yield

    if is_ci and HAS_GUARDRAILS and network_deny_guard:
        network_deny_guard.deactivate()


@pytest.fixture(autouse=True)
def reset_sync_guard():
    """Reset sync guard before each test (for test isolation)."""
    # Note: We intentionally DON'T reset between tests to enforce single-sync
    # across the entire session. This fixture is here for documentation.
    yield
