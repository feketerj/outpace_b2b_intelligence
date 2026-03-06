from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
import threading
import time
import logging
from backend.utils.secrets import get_secret

logger = logging.getLogger(__name__)

# Global database instance - thread-safe initialization
_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None
_init_lock = threading.Lock()

_MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2  # seconds


def init_database(mongo_url: str = None, db_name: str = None) -> AsyncIOMotorDatabase:
    """
    Initialize the database client. Called once at startup.
    Thread-safe: uses lock to prevent race condition during init.
    Retries up to 3 times with exponential backoff on connection failure.
    """
    global _client, _db

    with _init_lock:
        if _db is not None:
            return _db

        mongo_url = mongo_url or get_secret('MONGO_URL', default='mongodb://localhost:27017')
        db_name = db_name or get_secret('DB_NAME', default='outpace_intelligence')
        write_concern = get_secret('WRITE_CONCERN', default='majority')

        last_exc = None
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            try:
                _client = AsyncIOMotorClient(
                    mongo_url,
                    maxPoolSize=50,
                    minPoolSize=5,
                    maxIdleTimeMS=45000,
                    serverSelectionTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True,
                    w=write_concern,
                    readPreference='primaryPreferred',
                )
                _db = _client[db_name]
                logger.info(
                    "[database] Connected to MongoDB (attempt %d/%d) db=%s "
                    "retryWrites=True retryReads=True w=%s readPreference=primaryPreferred",
                    attempt, _MAX_RETRY_ATTEMPTS, db_name, write_concern
                )
                return _db
            except Exception as exc:
                last_exc = exc
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "[database] Connection attempt %d/%d failed: %s — retrying in %ss",
                    attempt, _MAX_RETRY_ATTEMPTS, exc, delay
                )
                if attempt < _MAX_RETRY_ATTEMPTS:
                    # init_database is intentionally synchronous (called at startup,
                    # outside any running event loop), so time.sleep is correct here.
                    time.sleep(delay)

        logger.error(
            "[database] All %d connection attempts failed. Last error: %s",
            _MAX_RETRY_ATTEMPTS, last_exc
        )
        raise RuntimeError(
            f"Failed to connect to MongoDB after {_MAX_RETRY_ATTEMPTS} attempts: {last_exc}"
        ) from last_exc


def get_database() -> AsyncIOMotorDatabase:
    """
    Get database instance. Must be initialized first via init_database().
    Auto-initializes with a warning if called before init_database().
    """
    global _db
    if _db is None:
        logger.warning(
            "[database] get_database() called before init_database(). "
            "Auto-initializing, but this indicates a startup order issue."
        )
        return init_database()
    return _db


def close_database():
    """Close database connection and reset global state."""
    global _client, _db
    with _init_lock:
        if _client:
            _client.close()
            logger.info("[database] MongoDB connection closed.")
            _client = None
            _db = None
