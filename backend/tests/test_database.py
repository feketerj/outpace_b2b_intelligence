"""
Unit tests for backend/database.py

Covers: successful init, retry behavior, get_database, close_database.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestInitDatabase:
    """Database initialization with retry logic."""

    def setup_method(self):
        """Reset global DB state before each test."""
        import backend.database as db_module
        db_module._client = None
        db_module._db = None

    def test_successful_init_returns_db(self):
        import backend.database as db_module

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("backend.database.AsyncIOMotorClient", return_value=mock_client):
            result = db_module.init_database("mongodb://localhost:27017", "test_db")

        assert result is mock_db

    def test_returns_existing_db_on_second_call(self):
        """Thread-safety: second call returns the cached db."""
        import backend.database as db_module

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("backend.database.AsyncIOMotorClient", return_value=mock_client):
            first = db_module.init_database("mongodb://localhost:27017", "test_db")
            second = db_module.init_database("mongodb://localhost:27017", "test_db")

        assert first is second

    def test_retries_on_failure_then_raises(self):
        """Exhausting retries raises RuntimeError."""
        import backend.database as db_module

        with patch("backend.database.AsyncIOMotorClient", side_effect=Exception("refused")):
            with patch("backend.database.time.sleep"):  # Don't actually sleep
                with pytest.raises(RuntimeError, match="Failed to connect"):
                    db_module.init_database("mongodb://bad:27017", "test_db")

    def test_succeeds_on_second_attempt(self):
        """Retry succeeds on second attempt."""
        import backend.database as db_module

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        call_count = 0

        def flaky_client(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("transient")
            return mock_client

        with patch("backend.database.AsyncIOMotorClient", side_effect=flaky_client):
            with patch("backend.database.time.sleep"):
                result = db_module.init_database("mongodb://localhost:27017", "test_db")

        assert result is mock_db
        assert call_count == 2


class TestGetDatabase:
    """get_database helper."""

    def setup_method(self):
        import backend.database as db_module
        db_module._client = None
        db_module._db = None

    def test_returns_cached_db(self):
        import backend.database as db_module

        mock_db = MagicMock()
        db_module._db = mock_db

        result = db_module.get_database()
        assert result is mock_db

    def test_auto_initializes_when_not_set(self):
        import backend.database as db_module

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        with patch("backend.database.AsyncIOMotorClient", return_value=mock_client):
            result = db_module.get_database()

        assert result is mock_db


class TestCloseDatabase:
    """close_database resets global state."""

    def setup_method(self):
        import backend.database as db_module
        db_module._client = None
        db_module._db = None

    def test_close_resets_global_state(self):
        import backend.database as db_module

        mock_client = MagicMock()
        mock_db = MagicMock()
        db_module._client = mock_client
        db_module._db = mock_db

        db_module.close_database()

        mock_client.close.assert_called_once()
        assert db_module._client is None
        assert db_module._db is None

    def test_close_when_not_connected_does_not_raise(self):
        import backend.database as db_module

        # Already None
        db_module.close_database()  # Should not raise
