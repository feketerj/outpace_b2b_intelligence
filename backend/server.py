from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from routes import auth, tenants, opportunities, intelligence, users, admin, chat, exports, config, upload
from scheduler.sync_scheduler import start_scheduler, stop_scheduler

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting OutPace Intelligence Platform")
    await init_db()
    start_scheduler(db)
    logger.info("Application startup complete")
    yield
    # Shutdown
    stop_scheduler()
    client.close()
    logger.info("Application shutdown complete")

app = FastAPI(
    title="OutPace Intelligence API",
    description="Multi-Tenant B2B Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Create API router
api_router = APIRouter(prefix="/api")

# Include route modules
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["Opportunities"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["Intelligence"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(exports.router, prefix="/exports", tags=["Exports"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

async def init_db():
    """Initialize database with indexes and default super admin"""
    logger.info("Initializing database indexes...")
    
    # Tenants collection indexes
    await db.tenants.create_index("slug", unique=True)
    await db.tenants.create_index("name")
    await db.tenants.create_index("status")
    
    # Users collection indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("tenant_id")
    await db.users.create_index([('tenant_id', 1), ('role', 1)])
    
    # Opportunities collection indexes
    await db.opportunities.create_index([('tenant_id', 1), ('captured_date', -1)])
    await db.opportunities.create_index([('tenant_id', 1), ('external_id', 1)], unique=True)
    await db.opportunities.create_index([('tenant_id', 1), ('score', -1)])
    await db.opportunities.create_index([('tenant_id', 1), ('due_date', 1)])
    await db.opportunities.create_index([('naics_code', 1)])
    await db.opportunities.create_index([("title", "text"), ("description", "text")])
    
    # Intelligence collection indexes
    await db.intelligence.create_index([('tenant_id', 1), ('created_at', -1)])
    await db.intelligence.create_index([('tenant_id', 1), ('type', 1)])
    
    # Chat messages collection indexes
    await db.chat_messages.create_index([('tenant_id', 1), ('conversation_id', 1), ('created_at', 1)])
    
    # Sync logs collection indexes
    await db.sync_logs.create_index([('tenant_id', 1), ('sync_timestamp', -1)])
    
    logger.info("Database indexes created successfully")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()