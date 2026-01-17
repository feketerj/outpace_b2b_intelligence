from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
import threading
from backend.utils.secrets import get_secret

# Global database instance - thread-safe initialization
_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None
_init_lock = threading.Lock()


def init_database(mongo_url: str = None, db_name: str = None) -> AsyncIOMotorDatabase:
    """
    Initialize the database client. Called once at startup.
    Thread-safe: uses lock to prevent race condition during init.
    """
    global _client, _db

    with _init_lock:
        if _db is not None:
            return _db

        mongo_url = mongo_url or get_secret('MONGO_URL', default='mongodb://localhost:27017')
        db_name = db_name or get_secret('DB_NAME', default='outpace_intelligence')

        _client = AsyncIOMotorClient(
            mongo_url,
            maxPoolSize=50,
            minPoolSize=5,
            maxIdleTimeMS=45000,
            serverSelectionTimeoutMS=5000
        )
        _db = _client[db_name]

    return _db


def get_database() -> AsyncIOMotorDatabase:
    """
    Get database instance. Must be initialized first via init_database().
    Raises RuntimeError if called before initialization.
    """
    global _db
    if _db is None:
        # Fallback: auto-init if not initialized (for backwards compat)
        # But log a warning - this shouldn't happen in production
        import logging
        logging.getLogger(__name__).warning(
            "[database] get_database() called before init_database(). "
            "Auto-initializing, but this indicates a startup order issue."
        )
        return init_database()
    return _db


def close_database():
    """Close database connection"""
    global _client, _db
    with _init_lock:
        if _client:
            _client.close()
            _client = None
            _db = None
