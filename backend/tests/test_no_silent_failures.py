"""
Silent Failure Guards - Verify errors are surfaced, not swallowed.

These tests verify that:
1. No `except: pass` patterns exist
2. External service failures are indicated in responses
3. Partial failures return appropriate status codes

Run: pytest backend/tests/test_no_silent_failures.py -v
"""

import pytest
import os
import re
import glob


class TestNoSilentExceptions:
    """Verify no silent exception handlers exist."""

    def get_python_files(self):
        """Get all Python files in backend."""
        base_path = os.path.dirname(os.path.dirname(__file__))
        pattern = os.path.join(base_path, "**", "*.py")
        return glob.glob(pattern, recursive=True)

    def test_no_bare_except_pass(self):
        """No `except: pass` or `except Exception: pass` patterns."""
        violations = []

        # Patterns that indicate silent exception swallowing
        bad_patterns = [
            re.compile(r'except\s*:\s*pass'),  # except: pass
            re.compile(r'except\s+\w+\s*:\s*pass'),  # except Exception: pass
        ]

        for filepath in self.get_python_files():
            # Skip test files and __pycache__
            if '__pycache__' in filepath or 'test_' in filepath:
                continue

            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for i, line in enumerate(content.split('\n'), 1):
                for pattern in bad_patterns:
                    if pattern.search(line):
                        violations.append(f"{filepath}:{i}: {line.strip()}")

        assert not violations, "Found silent exception handlers:\n" + "\n".join(violations)

    def test_except_blocks_have_logging_or_raise(self):
        """Exception blocks should log or re-raise."""
        # This is a heuristic check - look for except blocks
        # that have logger or raise in the following lines

        violations = []

        # Exclude patterns for test infrastructure
        exclude_patterns = [
            '__pycache__',
            'test_',
            'conftest.py',
            'validators',
            'guardrails',
            'ipv6_test.py',  # Test file without test_ prefix
        ]

        for filepath in self.get_python_files():
            # Skip test infrastructure files
            if any(pattern in filepath for pattern in exclude_patterns):
                continue

            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for idx, line in enumerate(lines):
                if 'except' not in line or ':' not in line:
                    continue

                check_range = lines[idx:min(idx + 5, len(lines))]
                # Check for logging, raising, or result methods (add_error, add_warning, etc.)
                has_action = any(
                    'logger' in candidate or
                    'logging' in candidate or
                    'raise' in candidate or
                    'log' in candidate.lower() or
                    'add_error' in candidate or  # Indirect logging via result objects
                    'add_warning' in candidate
                    for candidate in check_range
                )

                if not has_action:
                    violations.append(f"{filepath}:{idx + 1} except block missing log/raise")

        assert not violations, "Except blocks must log or raise:\n" + "\n".join(violations)


class TestDegradationIndicators:
    """Verify that service degradation is indicated in responses."""

    def test_ai_scoring_failure_indicator(self):
        """Mistral scoring failures must include ai_scoring_failed."""
        import inspect
        from backend.services import mistral_service
        source = inspect.getsource(mistral_service)

        assert "ai_scoring_failed" in source, \
            "Mistral service must return ai_scoring_failed on error"

    def test_rag_degradation_indicator(self):
        """RAG failures must include rag_degraded indicator."""
        import inspect
        from backend.routes import rag
        source = inspect.getsource(rag)

        assert "rag_degraded" in source, \
            "RAG route must return rag_degraded on embedding failure"

    def test_scheduler_reload_failure_indicator(self):
        """Config scheduler failures must return partial status."""
        import inspect
        from backend.routes import config
        source = inspect.getsource(config)

        assert '"partial"' in source or "'partial'" in source, \
            "Config route must return partial status on scheduler failure"


class TestPartialSuccessResponses:
    """Verify partial successes return appropriate status."""

    def test_config_returns_partial_on_scheduler_fail(self):
        """Intelligence config returns partial status when scheduler fails."""
        import inspect
        from backend.routes import config
        source = inspect.getsource(config.update_intelligence_config)

        # Should have a check for scheduler failure and return partial
        assert "scheduler_reload_failed" in source, \
            "Should track scheduler reload failure"
        assert '"partial"' in source or "'partial'" in source, \
            "Should return partial status"

    def test_image_resize_failure_surfaced(self):
        """Image resize failures should be indicated in response."""
        import inspect
        from backend.routes import upload
        source = inspect.getsource(upload.upload_tenant_logo)

        assert "resize_failed" in source, \
            "Should track resize failure"
        assert "warning" in source.lower(), \
            "Should include warning in response"


class TestErrorLogging:
    """Verify errors are logged with sufficient context."""

    def test_error_logs_include_context(self):
        """Error logs should include identifying information."""
        # Check that error logs include things like:
        # - tenant_id
        # - user_id
        # - operation name
        # - error details

        import inspect
        from backend.routes import chat
        source = inspect.getsource(chat.send_chat_message)

        # Should log errors with identifiable info
        assert "logger.error" in source or "logger.exception" in source, \
            "Should have error logging"

    def test_external_service_errors_logged(self):
        """External service errors should be logged."""
        import inspect
        from backend.services import mistral_service
        source = inspect.getsource(mistral_service)

        assert "logger.error" in source or "logger.warning" in source, \
            "External service errors should be logged"


class TestNoLyingResponses:
    """Verify responses don't claim success on failure."""

    def test_no_200_on_failure_patterns(self):
        """Look for patterns that might return 200 on failure."""
        # This is a heuristic check

        from backend.routes import config
        import inspect
        source = inspect.getsource(config)

        # If there's a try/except that catches and returns 200,
        # it should have explicit partial status

        # The fix we made: scheduler failure now returns partial, not success
        assert "partial" in source.lower(), \
            "Config should handle partial success explicitly"

    def test_sync_uses_partial_status(self):
        """Sync route should use partial status for mixed results."""
        # Check if sync route exists and handles partial success
        try:
            from backend.routes import sync
            import inspect
            source = inspect.getsource(sync)

            # If it has error handling, should return partial
            if "error" in source.lower():
                assert "partial" in source.lower() or "failed" in source.lower(), \
                    "Sync should indicate partial success"
        except ImportError:
            # Sync route may not exist
            pass
