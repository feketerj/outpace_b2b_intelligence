from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from backend.routes import auth, tenants, opportunities, intelligence, users, admin, chat, exports, config, upload, sync, rag, health
from backend.scheduler.sync_scheduler import start_scheduler, stop_scheduler
from backend.utils.preflight import run_preflight_checks
from backend.utils.auth import decode_token
from backend.utils.tracing import TracingMiddleware, setup_traced_logging, get_trace_id
from backend.utils.error_notifier import notify_error
from backend.utils.rate_limit import limiter, rate_limit_exceeded_handler
from backend.utils.migrations import run_migrations
from backend.utils.telemetry import setup_telemetry
from backend.database import init_database, get_database, close_database
from slowapi.errors import RateLimitExceeded

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure traced logging (adds trace_id to all log messages)
setup_traced_logging(logging.INFO)
logger = logging.getLogger(__name__)

async def _cleanup_stuck_rag_documents():
    """Cleanup stuck RAG documents from failed ingestions (status=processing older than 5 min)."""
    from datetime import datetime, timezone, timedelta
    db = get_database()
    threshold = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    stuck_docs = await db.kb_documents.find({"status": "processing", "created_at": {"$lt": threshold}}).to_list(100)
    for doc in stuck_docs:
        doc_id = doc.get("id")
        await db.kb_chunks.delete_many({"document_id": doc_id})
        await db.kb_documents.delete_one({"id": doc_id})
        logger.warning(f"[rag.cleanup] Deleted stuck document {doc_id} and its chunks")

    if stuck_docs:
        logger.info(f"[rag.cleanup] Cleaned up {len(stuck_docs)} stuck documents")


async def _ensure_rag_indexes():
    """Ensure indexes for RAG performance."""
    db = get_database()
    await db.kb_chunks.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.kb_chunks.create_index([("tenant_id", 1), ("document_id", 1)])
    await db.kb_documents.create_index([("tenant_id", 1), ("created_at", -1)])
    logger.info("[rag.indexes] RAG indexes ensured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === PREFLIGHT FIRST - Exit if critical failure ===
    await run_preflight_checks()

    # Startup (only reached if preflight passes)
    logger.info("Starting OutPace Intelligence Platform")

    # Initialize database ONCE at startup - prevents race condition
    init_database()

    await init_db()
    await run_migrations(get_database())
    await _cleanup_stuck_rag_documents()
    await _ensure_rag_indexes()
    start_scheduler(get_database())
    logger.info("Application startup complete")
    yield
    # Shutdown
    stop_scheduler()
    close_database()
    logger.info("Application shutdown complete")

app = FastAPI(
    title="OutPace Intelligence API",
    description="Multi-Tenant B2B Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize OpenTelemetry (if enabled via OTEL_ENABLED=true)
setup_telemetry(app)


@app.middleware("http")
async def enforce_tenant_status(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api/auth")
        or path.startswith("/api/health")
        or path.startswith("/docs")
        or path.startswith("/openapi")
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return await call_next(request)

    token = auth_header.split(" ", 1)[1].strip()
    try:
        token_data = decode_token(token)
    except Exception:
        # Invalid/expired token - silently proceed (endpoint will log auth failure)
        return await call_next(request)

    if token_data.role == "super_admin":
        return await call_next(request)

    if not token_data.tenant_id:
        return JSONResponse(status_code=403, content={"detail": "Tenant access required"})

    db = get_database()
    tenant = await db.tenants.find_one({"id": token_data.tenant_id}, {"_id": 0, "status": 1})
    if not tenant or tenant.get("status") != "active":
        return JSONResponse(status_code=403, content={"detail": "Tenant is suspended or inactive"})

    return await call_next(request)

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

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
api_router.include_router(sync.router, prefix="/sync", tags=["Sync"])
api_router.include_router(rag.router, prefix="/tenants", tags=["RAG"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])

app.include_router(api_router)

# TracingMiddleware FIRST (outermost layer) - adds trace_id to all requests
app.add_middleware(TracingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://localhost:3333,http://host.docker.internal:3000').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTPException with trace_id for debugging.

    All HTTP errors (400, 401, 403, 404, 422, etc.) include trace_id
    so users can report issues with a reference ID.
    """
    trace_id = get_trace_id()

    # Log 4xx as warnings, 5xx as errors
    log_level = logging.WARNING if exc.status_code < 500 else logging.ERROR
    logger.log(
        log_level,
        "http_exception",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path),
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors with trace_id.

    Returns detailed validation errors with trace_id for debugging.
    """
    trace_id = get_trace_id()

    logger.warning(
        "validation_error",
        extra={
            "errors": exc.errors(),
            "path": str(request.url.path),
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler. Emails you when prod breaks.

    - Logs the error with trace_id for correlation
    - Sends email alert if configured
    - Returns generic error to client (no stack traces leaked)
    """
    trace_id = get_trace_id()

    # Log locally first (always)
    logger.error(
        "uncaught_exception",
        exc_info=True,
        extra={
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": str(request.url.path),
            "method": request.method
        }
    )

    # Email alert (only if configured)
    notify_error(
        exc,
        request_info={
            "method": request.method,
            "path": str(request.url.path),
            "trace_id": trace_id,
            "client": request.client.host if request.client else "unknown",
        }
    )

    # Return generic error to client - no stack traces
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "trace_id": trace_id,
        },
        headers={"X-Trace-ID": trace_id}
    )


async def init_db():
    """Initialize database with indexes and default super admin"""
    logger.info("Initializing database indexes...")
    db = get_database()

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

    # External API usage and cost tracking indexes
    await db.external_api_usage.create_index([('tenant_id', 1), ('service', 1), ('timestamp', -1)])
    await db.tenant_costs.create_index([('tenant_id', 1), ('month', 1), ('service', 1)], unique=True)

    # Migrations collection
    await db.migrations.create_index("id", unique=True)

    # Refresh tokens collection indexes
    await db.refresh_tokens.create_index([("user_id", 1), ("revoked", 1)])
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("expires_at")  # For cleanup of expired tokens

    logger.info("Database indexes created successfully")

@app.get("/health")
async def health_check():
    """
    Enhanced health check with database connectivity verification.
    Returns 503 if database is unreachable.
    """
    from fastapi.responses import JSONResponse

    db = get_database()
    db_status = "healthy"
    overall_status = "healthy"

    try:
        # Ping database to verify connectivity
        await db.command("ping")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        overall_status = "degraded"
        logger.error(f"[health] Database ping failed: {e}")

    response = {
        "status": overall_status,
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if overall_status != "healthy":
        return JSONResponse(status_code=503, content=response)

    return response

@app.on_event("shutdown")
async def shutdown_db_client():
    close_database()