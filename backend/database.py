from motor.motor_asyncio import AsyncIOMotorClient
import os

# Global database instance
_client = None
_db = None

def get_database():
    """Get database instance"""
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'outpace_intelligence')
        _client = AsyncIOMotorClient(mongo_url)
        _db = _client[db_name]
    return _db

def close_database():
    """Close database connection"""
    global _client
    if _client:
        _client.close()
