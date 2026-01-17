"""
Preflight Check Tests - Verify startup validation works correctly.

Run: pytest backend/tests/test_preflight.py -v
"""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock


class TestPreflightEnvVars:
    """Test environment variable validation."""

    def test_missing_mongo_url_is_error(self):
        """Missing MONGO_URL should be a critical error."""
        from backend.utils.preflight import PreflightResult, _check_required_env_vars

        result = PreflightResult()

        with patch.dict(os.environ, {"MONGO_URL": "", "DB_NAME": "test", "JWT_SECRET": "secret"}, clear=True):
            _check_required_env_vars(result)

        assert result.critical_failure
        assert any("MONGO_URL" in e for e in result.errors)

    def test_missing_jwt_secret_is_error(self):
        """Missing JWT_SECRET should be a critical error."""
        from backend.utils.preflight import PreflightResult, _check_required_env_vars

        result = PreflightResult()

        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost", "DB_NAME": "test", "JWT_SECRET": ""}, clear=True):
            _check_required_env_vars(result)

        assert result.critical_failure
        assert any("JWT_SECRET" in e for e in result.errors)

    def test_missing_db_name_is_error(self):
        """Missing DB_NAME should be a critical error."""
        from backend.utils.preflight import PreflightResult, _check_required_env_vars

        result = PreflightResult()

        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost", "DB_NAME": "", "JWT_SECRET": "secret"}, clear=True):
            _check_required_env_vars(result)

        assert result.critical_failure
        assert any("DB_NAME" in e for e in result.errors)

    def test_all_env_vars_present_passes(self):
        """All required env vars present should pass."""
        from backend.utils.preflight import PreflightResult, _check_required_env_vars

        result = PreflightResult()

        with patch.dict(os.environ, {
            "MONGO_URL": "mongodb://localhost",
            "DB_NAME": "test",
            "JWT_SECRET": "secret-key-here"
        }, clear=True):
            _check_required_env_vars(result)

        assert not result.critical_failure
        assert result.checks_passed == 3


class TestJWTSecretQuality:
    """Test JWT secret quality warnings."""

    def test_dev_secret_triggers_warning(self):
        """Development secret pattern should trigger warning."""
        from backend.utils.preflight import PreflightResult, _check_jwt_secret_quality

        result = PreflightResult()

        with patch.dict(os.environ, {"JWT_SECRET": "local-dev-secret-key"}, clear=True):
            _check_jwt_secret_quality(result)

        assert len(result.warnings) > 0
        assert any("local-dev" in w for w in result.warnings)

    def test_test_secret_triggers_warning(self):
        """Test secret pattern should trigger warning."""
        from backend.utils.preflight import PreflightResult, _check_jwt_secret_quality

        result = PreflightResult()

        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}, clear=True):
            _check_jwt_secret_quality(result)

        assert len(result.warnings) > 0

    def test_short_secret_triggers_warning(self):
        """Short secret should trigger warning."""
        from backend.utils.preflight import PreflightResult, _check_jwt_secret_quality

        result = PreflightResult()

        with patch.dict(os.environ, {"JWT_SECRET": "short"}, clear=True):
            _check_jwt_secret_quality(result)

        assert len(result.warnings) > 0
        assert any("32 chars" in w for w in result.warnings)

    def test_good_secret_passes(self):
        """Good secret (>= 32 chars, no dev patterns) should pass."""
        from backend.utils.preflight import PreflightResult, _check_jwt_secret_quality

        result = PreflightResult()

        with patch.dict(os.environ, {"JWT_SECRET": "a" * 64}, clear=True):
            _check_jwt_secret_quality(result)

        assert len(result.warnings) == 0
        assert result.checks_passed == 1


class TestCORSSecurity:
    """Test CORS security - warnings in dev, HARD FAIL in production."""

    def test_missing_cors_origins_warns_in_development(self):
        """Missing CORS_ORIGINS in development mode should warn but not error."""
        from backend.utils.preflight import PreflightResult, _check_cors_security

        result = PreflightResult()

        # Development mode (default) - should warn, not error
        with patch.dict(os.environ, {"ENV": "development"}, clear=True):
            _check_cors_security(result)

        assert len(result.warnings) > 0
        assert not result.critical_failure  # Should NOT be a critical error in dev
        assert any("ANY origin" in w for w in result.warnings)

    def test_wildcard_cors_warns_in_development(self):
        """Explicit CORS_ORIGINS='*' in development should warn but not error."""
        from backend.utils.preflight import PreflightResult, _check_cors_security

        result = PreflightResult()

        with patch.dict(os.environ, {"CORS_ORIGINS": "*", "ENV": "development"}, clear=True):
            _check_cors_security(result)

        assert len(result.warnings) > 0
        assert not result.critical_failure  # Should NOT be a critical error in dev

    def test_wildcard_cors_fails_hard_in_production(self):
        """CRITICAL: Wildcard CORS in production must be a HARD FAILURE."""
        from backend.utils.preflight import PreflightResult, _check_cors_security

        result = PreflightResult()

        # Production mode with wildcard - must FAIL
        with patch.dict(os.environ, {"CORS_ORIGINS": "*", "ENV": "production"}, clear=True):
            _check_cors_security(result)

        assert result.critical_failure  # MUST be a critical error
        assert any("production" in e.lower() for e in result.errors)
        assert any("will not start" in e.lower() for e in result.errors)

    def test_missing_cors_fails_hard_in_production(self):
        """CRITICAL: Missing CORS_ORIGINS in production must be a HARD FAILURE."""
        from backend.utils.preflight import PreflightResult, _check_cors_security

        result = PreflightResult()

        # Production mode with no CORS config - must FAIL
        with patch.dict(os.environ, {"ENV": "prod"}, clear=True):
            _check_cors_security(result)

        assert result.critical_failure  # MUST be a critical error
        assert len(result.errors) > 0

    def test_explicit_origin_passes_in_production(self):
        """Explicit CORS_ORIGINS in production should pass."""
        from backend.utils.preflight import PreflightResult, _check_cors_security

        result = PreflightResult()

        with patch.dict(os.environ, {
            "CORS_ORIGINS": "https://myapp.com",
            "ENV": "production"
        }, clear=True):
            _check_cors_security(result)

        assert not result.critical_failure
        assert len(result.warnings) == 0
        assert result.checks_passed == 1


class TestMongoDBConnectivity:
    """Test MongoDB connectivity checks."""

    @pytest.mark.asyncio
    async def test_successful_connection_passes(self):
        """Successful MongoDB connection should pass."""
        from backend.utils.preflight import PreflightResult, _check_mongodb_connectivity

        result = PreflightResult()

        # Mock successful connection (patch at import location inside function)
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.admin.command = AsyncMock(return_value={"ok": 1})
            mock_instance.close = MagicMock()
            mock_client.return_value = mock_instance

            with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017"}, clear=True):
                await _check_mongodb_connectivity(result, timeout_seconds=5.0)

        assert not result.critical_failure
        assert result.checks_passed == 1

    @pytest.mark.asyncio
    async def test_connection_failure_is_error(self):
        """MongoDB connection failure should be a critical error."""
        from backend.utils.preflight import PreflightResult, _check_mongodb_connectivity

        result = PreflightResult()

        # Mock failed connection (patch at import location inside function)
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.admin.command = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.return_value = mock_instance

            with patch.dict(os.environ, {"MONGO_URL": "mongodb://nonexistent:27017"}, clear=True):
                await _check_mongodb_connectivity(result, timeout_seconds=1.0)

        assert result.critical_failure
        assert any("connection failed" in e.lower() for e in result.errors)


class TestPreflightIntegration:
    """Integration tests for full preflight flow."""

    @pytest.mark.asyncio
    async def test_preflight_exits_on_critical_failure(self):
        """Preflight should exit with code 1 on critical failure."""
        from backend.utils.preflight import run_preflight_checks

        with patch.dict(os.environ, {"MONGO_URL": "", "DB_NAME": "", "JWT_SECRET": ""}, clear=True):
            with patch('sys.exit') as mock_exit:
                await run_preflight_checks(exit_on_failure=True)
                mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_preflight_returns_result_without_exit(self):
        """Preflight should return result when exit_on_failure=False."""
        from backend.utils.preflight import run_preflight_checks

        with patch.dict(os.environ, {"MONGO_URL": "", "DB_NAME": "", "JWT_SECRET": ""}, clear=True):
            result = await run_preflight_checks(exit_on_failure=False)

        assert result.critical_failure
        assert len(result.errors) >= 3  # At least 3 missing env vars

    @pytest.mark.asyncio
    async def test_preflight_passes_with_valid_config(self):
        """Preflight should pass with valid configuration."""
        from backend.utils.preflight import run_preflight_checks

        # Mock MongoDB connection (patch at import location inside function)
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.admin.command = AsyncMock(return_value={"ok": 1})
            mock_instance.close = MagicMock()
            mock_client.return_value = mock_instance

            with patch.dict(os.environ, {
                "MONGO_URL": "mongodb://localhost:27017",
                "DB_NAME": "test_db",
                "JWT_SECRET": "a" * 64  # Good secret
            }, clear=True):
                result = await run_preflight_checks(exit_on_failure=False)

        assert not result.critical_failure
        assert result.checks_passed >= 4  # ENV vars + JWT quality + MongoDB


class TestPreflightResult:
    """Test PreflightResult container."""

    def test_critical_failure_is_false_when_no_errors(self):
        """No errors means no critical failure."""
        from backend.utils.preflight import PreflightResult

        result = PreflightResult()
        result.add_pass("TEST_CHECK")
        result.add_warning("Some warning")

        assert not result.critical_failure

    def test_critical_failure_is_true_when_errors(self):
        """Any error means critical failure."""
        from backend.utils.preflight import PreflightResult

        result = PreflightResult()
        result.add_error("Some error")

        assert result.critical_failure

    def test_add_pass_increments_counter(self):
        """add_pass should increment checks_passed."""
        from backend.utils.preflight import PreflightResult

        result = PreflightResult()
        assert result.checks_passed == 0

        result.add_pass("CHECK_1")
        assert result.checks_passed == 1

        result.add_pass("CHECK_2")
        assert result.checks_passed == 2
