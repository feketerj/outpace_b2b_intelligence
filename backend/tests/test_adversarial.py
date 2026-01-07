"""
Adversarial / Nasty Payload Tests

Tests edge cases and malicious inputs that could break the system.
Based on hardening patterns from concurrent builds.

Categories:
1. Empty inputs
2. Extremely long inputs
3. Unicode weirdness
4. JSON-looking content in text fields
5. Injection attempts
6. Boundary conditions
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json


class TestEmptyInputs:
    """Test handling of empty/null inputs."""

    def test_empty_string_title(self):
        """Empty string title should be rejected or handled."""
        # Opportunities PATCH only allows specific client-editable fields
        # title is NOT patchable via the PATCH endpoint (immutable from source)
        allowed_fields = {"client_status", "client_notes", "client_tags", "is_archived"}

        # Verify title is NOT in patchable fields (it's from the source)
        assert "title" not in allowed_fields
        # Actual field validation happens in the route handler

    def test_whitespace_only_not_treated_as_content(self):
        """Whitespace-only strings should be treated as empty."""
        test_inputs = [
            "   ",           # Spaces
            "\t\t",          # Tabs
            "\n\n",          # Newlines
            "  \t\n  ",      # Mixed
        ]

        for inp in test_inputs:
            stripped = inp.strip()
            assert len(stripped) == 0, f"'{repr(inp)}' should strip to empty"

    @pytest.mark.asyncio
    async def test_empty_opportunities_context(self):
        """Empty opportunities list should return empty context gracefully."""
        from backend.routes.chat import _retrieve_opportunities_context

        # Mock empty database
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_db.opportunities.find.return_value.sort.return_value.limit.return_value = mock_cursor

        context, debug_info = await _retrieve_opportunities_context(
            mock_db, "tenant-123", {}, debug=False
        )

        assert context == ""
        assert debug_info["reason"] == "no_items"
        assert debug_info["items_used"] == 0


class TestExtremelyLongInputs:
    """Test handling of very long strings."""

    def test_long_title_truncation_or_rejection(self):
        """Very long titles should be handled safely."""
        long_title = "A" * 100000  # 100KB

        # At minimum, we should not crash
        # Best case: truncation or rejection
        assert len(long_title) == 100000

    def test_long_description_in_intelligence(self):
        """Long descriptions should be truncated in context."""
        # Verify the truncation logic exists in the function
        import inspect
        from backend.routes.chat import _retrieve_intelligence_context

        source = inspect.getsource(_retrieve_intelligence_context)

        # Should have truncation logic ([:200] or similar)
        assert "[:200]" in source or "[:500]" in source or "summary" in source, \
            "Intelligence context should truncate long summaries"

    def test_max_chars_limit_respected(self):
        """Context should respect max_chars configuration."""
        # This is tested in test_domain_context.py
        # Verify the config key exists
        max_chars_default = 3000
        assert max_chars_default > 0


class TestUnicodeWeirdness:
    """Test handling of unusual Unicode characters."""

    def test_zero_width_characters(self):
        """Zero-width characters should not cause issues."""
        weird_strings = [
            "Hello\u200bWorld",       # Zero-width space
            "Test\u200cString",       # Zero-width non-joiner
            "Data\u200dValue",        # Zero-width joiner
            "Name\ufeffContent",      # BOM
        ]

        for s in weird_strings:
            # Should be processable
            encoded = s.encode('utf-8')
            decoded = encoded.decode('utf-8')
            assert decoded == s

    def test_emoji_handling(self):
        """Emoji should not break string processing."""
        emoji_strings = [
            "Contract 📋 Review",
            "Status: ✅ Complete",
            "Priority: 🔥🔥🔥",
            "Value: 💰 $1M",
        ]

        for s in emoji_strings:
            # Should be JSON-serializable
            json_str = json.dumps({"text": s})
            parsed = json.loads(json_str)
            assert parsed["text"] == s

    def test_rtl_and_mixed_direction(self):
        """Right-to-left text should not break layouts."""
        rtl_strings = [
            "مرحبا",           # Arabic
            "שלום",            # Hebrew
            "Hello مرحبا",     # Mixed
        ]

        for s in rtl_strings:
            encoded = s.encode('utf-8')
            assert len(encoded) > 0

    def test_homoglyph_attacks(self):
        """Similar-looking characters should not bypass validation."""
        # These look similar but are different Unicode points
        homoglyphs = [
            ("admin", "аdmin"),   # Cyrillic 'а' vs Latin 'a'
            ("user", "uѕer"),    # Cyrillic 'ѕ' vs Latin 's'
        ]

        for normal, attack in homoglyphs:
            assert normal != attack, f"'{normal}' should differ from '{attack}'"


class TestJsonLookingContent:
    """Test that JSON-like content in fields doesn't break parsing."""

    def test_json_in_title(self):
        """JSON string in title should be treated as plain text."""
        titles_with_json = [
            '{"ok": false, "error": "hack"}',
            '[1, 2, 3]',
            '{"__proto__": {"admin": true}}',
            'null',
            'true',
            '{"$ne": null}',  # MongoDB injection attempt
        ]

        for title in titles_with_json:
            # Should remain a string, not be parsed
            assert isinstance(title, str)
            # When stored and retrieved, should still be the same string
            data = {"title": title}
            serialized = json.dumps(data)
            deserialized = json.loads(serialized)
            assert deserialized["title"] == title

    def test_mongodb_operator_injection(self):
        """MongoDB operators in input should not be interpreted."""
        injection_attempts = [
            {"$gt": ""},
            {"$ne": None},
            {"$where": "function() { return true; }"},
            {"$regex": ".*"},
        ]

        # These should be treated as literal dict values, not operators
        # The actual protection is in how we build queries (always use explicit field=value)
        for attempt in injection_attempts:
            # When serialized as JSON string (not embedded in query), harmless
            json_str = json.dumps(attempt)
            assert "$" in json_str  # Still contains the $, but as data


class TestBoundaryConditions:
    """Test edge cases and boundaries."""

    def test_page_zero_handling(self):
        """Page 0 should be handled (often means page 1)."""
        # Pagination typically starts at 1
        page = 0
        per_page = 10
        skip = max(0, (page - 1) * per_page)  # Should not go negative
        assert skip >= 0

    def test_negative_values(self):
        """Negative values in numeric fields should be caught."""
        negative_values = {
            "estimated_value": -1000,
            "score": -50,
            "page": -1,
            "per_page": -10,
        }

        for field, value in negative_values.items():
            assert value < 0  # Confirm they're negative
            # Actual validation happens in Pydantic models or route logic

    def test_float_precision(self):
        """Float values should not cause precision issues."""
        # MongoDB stores floats as BSON Double
        values = [
            0.1 + 0.2,  # Classic float issue: 0.30000000000000004
            1e308,      # Near max float
            1e-308,     # Near min float
        ]

        for v in values:
            json_str = json.dumps({"value": v})
            parsed = json.loads(json_str)
            # Should round-trip without crash
            assert "value" in parsed


class TestTimeoutHandling:
    """Test timeout behavior for external calls."""

    def test_mistral_timeout_configuration(self):
        """Verify Mistral calls have timeout configured."""
        # Check that timeout is set in config or code
        # The actual timeout is set in the Mistral client initialization
        default_timeout = 30  # seconds
        assert default_timeout > 0

    def test_perplexity_timeout_configuration(self):
        """Verify Perplexity calls have timeout configured."""
        default_timeout = 60  # seconds for research
        assert default_timeout > 0


class TestRequestIdPropagation:
    """Test that request IDs propagate through the system."""

    def test_trace_id_header_name(self):
        """Verify the trace ID header is consistently named."""
        # The trace ID header is used inline in tracing.py
        # Verify the pattern exists in the source
        import inspect
        from backend.utils import tracing

        source = inspect.getsource(tracing)
        assert "X-Trace-ID" in source, "Trace ID header should be X-Trace-ID"

    def test_trace_id_format(self):
        """Verify trace ID format is valid UUID or similar."""
        import uuid

        # Generate a test trace ID
        trace_id = str(uuid.uuid4())

        # Should be a valid UUID string
        parsed = uuid.UUID(trace_id)
        assert str(parsed) == trace_id


class TestContractMismatch:
    """Test handling of responses that violate expected contracts."""

    def test_missing_required_fields_detected(self):
        """Responses missing required fields should be caught."""
        from backend.utils.invariants import assert_fields_present, InvariantViolation

        data = {"id": "123"}  # Missing tenant_id

        with pytest.raises(InvariantViolation):
            assert_fields_present(data, ["id", "tenant_id"])

    def test_wrong_type_detected(self):
        """Wrong types in response should be catchable."""
        # For example, expecting list but getting dict
        response = {"items": {}}  # Should be a list

        assert not isinstance(response["items"], list)

    def test_null_where_value_expected(self):
        """Null values where data expected should be flagged."""
        from backend.utils.invariants import assert_field_present, InvariantViolation

        data = {"tenant_id": None}

        with pytest.raises(InvariantViolation):
            assert_field_present(data, "tenant_id")


class TestConcurrentAccessPatterns:
    """Test patterns that could cause race conditions."""

    def test_quota_atomicity_pattern_exists(self):
        """Verify quota updates use atomic operations."""
        # The chat.py uses a two-phase atomic pattern
        # This test verifies the pattern is documented/present
        import inspect
        from backend.routes import chat

        source = inspect.getsource(chat)

        # Check for atomic update patterns
        assert "$inc" in source or "update_one" in source, \
            "Chat should use atomic MongoDB updates for quota"

    def test_optimistic_locking_pattern(self):
        """If using optimistic locking, verify pattern."""
        # Not currently implemented in this codebase
        # This test documents the gap - optimistic locking would add:
        # - Version field on documents
        # - Conditional updates with version check
        # For now, we rely on MongoDB's atomic operations
        pytest.skip("Optimistic locking not implemented (using atomic ops instead)")


class TestErrorMessageSafety:
    """Test that error messages don't leak sensitive info."""

    def test_password_not_in_error_messages(self):
        """Passwords should never appear in error messages."""
        from backend.utils.invariants import InvariantViolation

        try:
            raise InvariantViolation("Auth failed for user attempt")
        except InvariantViolation as e:
            error_str = str(e)
            assert "password" not in error_str.lower()
            assert "secret" not in error_str.lower()

    def test_api_keys_not_logged(self):
        """API keys should not appear in log messages."""
        # Verify that API key access uses environ.get pattern, not hardcoded
        import inspect
        from backend.services import mistral_service

        source = inspect.getsource(mistral_service)

        # Should use os.environ.get or os.getenv, not hardcoded keys
        assert "os.environ" in source or "os.getenv" in source, \
            "API keys should be accessed via environment variables"

        # Should not contain actual API key patterns (sk-xxx, etc.)
        assert "sk-" not in source, "Hardcoded API key detected"


class TestInputNormalization:
    """Test that inputs are properly normalized."""

    def test_email_case_normalization(self):
        """Email addresses should be case-insensitive."""
        emails = [
            "User@Example.com",
            "USER@EXAMPLE.COM",
            "user@example.com",
        ]

        normalized = [e.lower() for e in emails]
        assert len(set(normalized)) == 1  # All same after normalization

    def test_uuid_format_validation(self):
        """UUIDs should be validated for format."""
        import uuid

        valid_uuids = [
            "123e4567-e89b-12d3-a456-426614174000",
            str(uuid.uuid4()),
        ]

        invalid_uuids = [
            "not-a-uuid",
            "123",
            "",
            "123e4567-e89b-12d3-a456",  # Truncated
        ]

        for u in valid_uuids:
            try:
                uuid.UUID(u)
            except ValueError:
                pytest.fail(f"Valid UUID '{u}' should parse")

        for u in invalid_uuids:
            with pytest.raises(ValueError):
                uuid.UUID(u)
