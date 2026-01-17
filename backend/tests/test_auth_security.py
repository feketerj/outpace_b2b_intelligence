"""
Tests for authentication security features:
- Password policy validation
- Refresh token flow
- Token revocation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.utils.auth import (
    validate_password_policy,
    generate_refresh_token,
    hash_refresh_token,
    create_access_token,
    create_refresh_token_jwt,
    decode_refresh_token,
    JWT_EXPIRATION_HOURS,
)


class TestPasswordPolicy:
    """Test password policy validation."""

    def test_valid_password(self):
        """Test that a strong password passes validation."""
        is_valid, errors = validate_password_policy("SecurePass123!")
        assert is_valid is True
        assert errors == []

    def test_password_too_short(self):
        """Test that short passwords are rejected."""
        is_valid, errors = validate_password_policy("Ab1!")
        assert is_valid is False
        assert any("at least 8 characters" in e for e in errors)

    def test_password_no_uppercase(self):
        """Test that passwords without uppercase are rejected."""
        is_valid, errors = validate_password_policy("securepass123!")
        assert is_valid is False
        assert any("uppercase" in e for e in errors)

    def test_password_no_lowercase(self):
        """Test that passwords without lowercase are rejected."""
        is_valid, errors = validate_password_policy("SECUREPASS123!")
        assert is_valid is False
        assert any("lowercase" in e for e in errors)

    def test_password_no_digit(self):
        """Test that passwords without digits are rejected."""
        is_valid, errors = validate_password_policy("SecurePassword!")
        assert is_valid is False
        assert any("digit" in e for e in errors)

    def test_password_no_special(self):
        """Test that passwords without special characters are rejected."""
        is_valid, errors = validate_password_policy("SecurePass123")
        assert is_valid is False
        assert any("special character" in e for e in errors)

    def test_password_multiple_failures(self):
        """Test that multiple policy failures are reported."""
        is_valid, errors = validate_password_policy("abc")
        assert is_valid is False
        assert len(errors) >= 3  # At least: length, uppercase, digit, special

    def test_password_with_various_special_chars(self):
        """Test various special characters are accepted."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for char in special_chars:
            is_valid, errors = validate_password_policy(f"SecurePass1{char}")
            assert is_valid is True, f"Special char '{char}' should be accepted"


class TestRefreshTokenGeneration:
    """Test refresh token generation and hashing."""

    def test_generate_refresh_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = [generate_refresh_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique

    def test_generate_refresh_token_length(self):
        """Test that generated tokens have sufficient entropy."""
        token = generate_refresh_token()
        # URL-safe base64 encoding of 32 bytes = ~43 chars
        assert len(token) >= 40

    def test_hash_refresh_token_deterministic(self):
        """Test that hashing is deterministic."""
        token = "test_token_12345"
        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)
        assert hash1 == hash2

    def test_hash_refresh_token_different_input(self):
        """Test that different tokens produce different hashes."""
        hash1 = hash_refresh_token("token1")
        hash2 = hash_refresh_token("token2")
        assert hash1 != hash2


class TestAccessToken:
    """Test access token creation."""

    def test_create_access_token_returns_tuple(self):
        """Test that create_access_token returns token and expiration."""
        data = {"sub": "user123", "email": "test@example.com", "role": "tenant_user"}
        token, expires = create_access_token(data)
        
        assert isinstance(token, str)
        assert isinstance(expires, datetime)
        assert expires > datetime.now(timezone.utc)

    def test_create_access_token_custom_expiry(self):
        """Test custom expiration delta."""
        data = {"sub": "user123", "email": "test@example.com", "role": "tenant_user"}
        custom_delta = timedelta(minutes=5)
        token, expires = create_access_token(data, expires_delta=custom_delta)
        
        expected_min = datetime.now(timezone.utc) + timedelta(minutes=4)
        expected_max = datetime.now(timezone.utc) + timedelta(minutes=6)
        
        assert expected_min < expires < expected_max


class TestRefreshTokenJWT:
    """Test refresh token JWT operations."""

    def test_create_refresh_token_jwt(self):
        """Test refresh token JWT creation."""
        data = {"sub": "user123"}
        token, expires = create_refresh_token_jwt(data)
        
        assert isinstance(token, str)
        assert isinstance(expires, datetime)
        assert expires > datetime.now(timezone.utc)

    def test_decode_valid_refresh_token(self):
        """Test decoding a valid refresh token."""
        data = {"sub": "user123"}
        token, _ = create_refresh_token_jwt(data)
        
        payload = decode_refresh_token(token)
        
        assert payload["user_id"] == "user123"
        assert "exp" in payload

    def test_decode_invalid_refresh_token(self):
        """Test that invalid tokens raise HTTPException."""
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token("invalid.token.here")
        
        assert exc_info.value.status_code == 401

    def test_decode_access_token_as_refresh_fails(self):
        """Test that access tokens cannot be used as refresh tokens."""
        from fastapi import HTTPException
        
        data = {"sub": "user123", "email": "test@example.com", "role": "tenant_user"}
        access_token, _ = create_access_token(data)
        
        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(access_token)
        
        assert exc_info.value.status_code == 401
        assert "token type" in str(exc_info.value.detail).lower()


class TestPasswordPolicyEdgeCases:
    """Edge cases for password policy."""

    def test_empty_password(self):
        """Test empty password is rejected."""
        is_valid, errors = validate_password_policy("")
        assert is_valid is False
        assert len(errors) >= 1

    def test_password_with_unicode(self):
        """Test password with unicode characters."""
        # Unicode letters don't count as ASCII uppercase/lowercase
        is_valid, errors = validate_password_policy("Пароль123!")
        # Should fail on uppercase/lowercase since we check ASCII
        assert is_valid is False

    def test_password_exactly_minimum_length(self):
        """Test password at exactly minimum length."""
        is_valid, errors = validate_password_policy("Abcd12!@")  # 8 chars
        assert is_valid is True
        assert errors == []

    def test_password_with_whitespace(self):
        """Test password with whitespace is accepted."""
        is_valid, errors = validate_password_policy("Secure Pass 123!")
        assert is_valid is True  # Whitespace is allowed


class TestTokenExpirationTimes:
    """Test token expiration configurations."""

    def test_access_token_expiration_within_range(self):
        """Test access token expires within configured hours."""
        data = {"sub": "user123", "email": "test@example.com", "role": "tenant_user"}
        _, expires = create_access_token(data)
        
        # Should be within JWT_EXPIRATION_HOURS +/- 1 minute
        expected = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
        delta = abs((expires - expected).total_seconds())
        assert delta < 60  # Within 1 minute

    def test_refresh_token_expiration_longer_than_access(self):
        """Test refresh token expires later than access token."""
        data = {"sub": "user123", "email": "test@example.com", "role": "tenant_user"}
        _, access_expires = create_access_token(data)
        _, refresh_expires = create_refresh_token_jwt(data)
        
        assert refresh_expires > access_expires
