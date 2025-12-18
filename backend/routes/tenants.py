from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import List, Optional, Set
from datetime import datetime, timezone, timedelta
import uuid
import logging

from models import (
    Tenant, TenantCreate, TenantUpdate, PaginatedResponse, PaginationMetadata,
    TenantStatus
)
from utils.auth import get_current_super_admin, get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("", response_model=Tenant, dependencies=[Depends(get_current_super_admin)])
async def create_tenant(tenant_data: TenantCreate):
    """Create new tenant (Super Admin only)"""
    db = get_db()
    
    # Check if slug already exists
    existing_tenant = await db.tenants.find_one({"slug": tenant_data.slug})
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant slug already exists"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    tenant_doc = {
        "id": str(uuid.uuid4()),
        **tenant_data.model_dump(),
        "created_at": now,
        "updated_at": now,
        "last_synced_at": None,
        "rate_limit_used": 0,
        "rate_limit_monthly": 500,
        "rate_limit_reset_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }
    
    await db.tenants.insert_one(tenant_doc)
    return Tenant(**tenant_doc)

@router.get("", response_model=PaginatedResponse)
async def list_tenants(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[TenantStatus] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """List all tenants with pagination"""
    db = get_db()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"slug": {"$regex": search, "$options": "i"}}
        ]
    
    # Non-super admins only see their own tenant
    if current_user.role != "super_admin" and current_user.tenant_id:
        query["id"] = current_user.tenant_id
    
    # Get total count
    total = await db.tenants.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * per_page
    cursor = db.tenants.find(query, {"_id": 0}).skip(skip).limit(per_page).sort("created_at", -1)
    tenants = await cursor.to_list(length=per_page)
    
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse(
        data=[Tenant(**t) for t in tenants],
        pagination=PaginationMetadata(
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
    )

@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(tenant_id: str, current_user: TokenData = Depends(get_current_user)):
    """Get tenant by ID"""
    db = get_db()
    
    # Check permissions - allow tenant users to view their own tenant
    if current_user.role not in ["super_admin", "tenant_admin"] and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant_doc = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    
    if not tenant_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return Tenant(**tenant_doc)

def deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge updates into base, preserving unspecified nested fields."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# COMPLETE schema of ALL allowed fields at EVERY level
# This is the SINGLE SOURCE OF TRUTH for what the API accepts

ALLOWED_TOP_LEVEL_FIELDS: Set[str] = {
    "name", "slug", "status", "branding", "search_profile", "scoring_weights",
    "agent_config", "intelligence_config", "chat_policy", "tenant_knowledge", "rag_policy"
}

ALLOWED_NESTED_FIELDS = {
    "scoring_weights": {"value_weight", "deadline_weight", "relevance_weight"},
    "chat_policy": {"enabled", "monthly_message_limit", "max_user_chars", "max_assistant_tokens", "max_turns_history"},
    "rag_policy": {"enabled", "max_documents", "max_chunks", "top_k", "min_score", "max_context_chars", "embed_model"},
    "branding": {
        "logo_url", "logo_base64", "primary_color", "secondary_color", "accent_color",
        "text_color", "background_image_url", "background_image_base64", "visual_theme",
        "enable_glow_effects", "enable_sheen_overlay", "company_name"
    },
    "search_profile": {
        "naics_codes", "keywords", "interest_areas", "competitors", "highergov_api_key",
        "highergov_search_id", "fetch_full_documents", "fetch_nsn", "fetch_grants",
        "fetch_contracts", "auto_update_enabled", "auto_update_interval_hours", "agencies", "set_asides", "competition_types"
    },
    "agent_config": {
        "scoring_agent_id", "opportunities_chat_agent_id", "intelligence_chat_agent_id",
        "scoring_instructions", "opportunities_chat_instructions", "intelligence_chat_instructions",
        "scoring_output_schema"
    },
    "intelligence_config": {
        "enabled", "perplexity_prompt_template", "schedule_cron", "lookback_days",
        "deadline_window_days", "target_sources", "report_sections", "scoring_weights"
    },
    "tenant_knowledge": {"snippets", "last_updated"},
}


def find_all_unknown_fields(data: dict) -> list:
    """
    Recursively find ALL unknown fields in the payload.
    Returns list of dotted paths to unknown fields.
    """
    unknown = []
    
    # Check top-level fields
    for key in data.keys():
        if key not in ALLOWED_TOP_LEVEL_FIELDS:
            unknown.append(key)
        elif key in ALLOWED_NESTED_FIELDS and isinstance(data[key], dict):
            # Check nested fields
            allowed_subfields = ALLOWED_NESTED_FIELDS[key]
            for subkey in data[key].keys():
                if subkey not in allowed_subfields:
                    unknown.append(f"{key}.{subkey}")
    
    return unknown


@router.patch("/{tenant_id}", response_model=Tenant)
async def patch_tenant(
    tenant_id: str,
    request: Request,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """
    PATCH tenant with deep merge.
    
    CRITICAL: Unknown fields are REJECTED with HTTP 400.
    The system will NEVER return success while dropping data.
    """
    db = get_db()
    
    # STEP 1: Get raw request body
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )
    
    if not payload or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a non-empty JSON object"
        )
    
    # STEP 2: REJECT unknown fields BEFORE any processing
    unknown_fields = find_all_unknown_fields(payload)
    if unknown_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown fields rejected: {', '.join(unknown_fields)}"
        )
    
    # STEP 3: Check tenant exists
    existing_tenant = await db.tenants.find_one({"id": tenant_id})
    if not existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # STEP 4: SECURITY - Block restricted fields for master tenants
    if existing_tenant.get("is_master_client"):
        for blocked in ["chat_policy", "tenant_knowledge", "rag_policy"]:
            if blocked in payload:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{blocked} cannot be modified for master tenants"
                )
    
    # STEP 5: Deep merge nested objects
    merged_data = {}
    for key, value in payload.items():
        if key in ALLOWED_NESTED_FIELDS and isinstance(value, dict):
            existing_value = existing_tenant.get(key, {}) or {}
            merged_data[key] = deep_merge(existing_value, value)
        else:
            merged_data[key] = value
    
    merged_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": merged_data}
    )
    
    updated_tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    return Tenant(**updated_tenant)


@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    request: Request,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """
    Update tenant (Super Admin only).
    PUT performs deep merge on nested config objects.
    
    CRITICAL: Unknown fields are REJECTED with HTTP 400.
    The system will NEVER return success while dropping data.
    """
    db = get_db()
    
    # STEP 1: Get raw request body BEFORE Pydantic strips unknown fields
    try:
        raw_body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )
    
    if not raw_body or not isinstance(raw_body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a non-empty JSON object"
        )
    
    # STEP 2: REJECT unknown fields BEFORE any processing
    unknown_fields = find_all_unknown_fields(raw_body)
    if unknown_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown fields rejected: {', '.join(unknown_fields)}"
        )
    
    # STEP 3: Check tenant exists
    existing_tenant = await db.tenants.find_one({"id": tenant_id})
    if not existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # STEP 4: Check slug uniqueness if updating
    if raw_body.get("slug") and raw_body.get("slug") != existing_tenant.get("slug"):
        slug_exists = await db.tenants.find_one({"slug": raw_body.get("slug")})
        if slug_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant slug already exists"
            )
    
    # STEP 5: SECURITY - Block restricted fields for master tenants
    if existing_tenant.get("is_master_client"):
        for blocked in ["chat_policy", "tenant_knowledge", "rag_policy"]:
            if blocked in raw_body:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{blocked} cannot be modified for master tenants"
                )
    
    # STEP 6: Deep merge nested objects (prevent sibling loss)
    merged_data = {}
    for key, value in raw_body.items():
        if key in ALLOWED_NESTED_FIELDS and isinstance(value, dict):
            existing_value = existing_tenant.get(key, {}) or {}
            merged_data[key] = deep_merge(existing_value, value)
        else:
            merged_data[key] = value
    
    merged_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": merged_data}
    )
    
    # Return updated tenant
    updated_tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    return Tenant(**updated_tenant)

@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Delete tenant (Super Admin only)"""
    db = get_db()
    
    result = await db.tenants.delete_one({"id": tenant_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Also delete related data
    await db.users.delete_many({"tenant_id": tenant_id})
    await db.opportunities.delete_many({"tenant_id": tenant_id})
    await db.intelligence.delete_many({"tenant_id": tenant_id})
    await db.chat_messages.delete_many({"tenant_id": tenant_id})
    await db.knowledge_snippets.delete_many({"tenant_id": tenant_id})
    
    return None


# ==================== KNOWLEDGE SNIPPETS (SUPER ADMIN ONLY) ====================

@router.get("/{tenant_id}/knowledge-snippets")
async def list_knowledge_snippets(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """List all knowledge snippets for a tenant (Super Admin only)"""
    db = get_db()
    
    cursor = db.knowledge_snippets.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).sort("created_at", -1)
    
    snippets = await cursor.to_list(length=100)
    return snippets


@router.post("/{tenant_id}/knowledge-snippets")
async def create_knowledge_snippet(
    tenant_id: str,
    snippet_data: dict,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Create a knowledge snippet (Super Admin only, not for master tenants)"""
    db = get_db()
    
    # Check tenant exists and is not master
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if tenant.get("is_master_client"):
        raise HTTPException(status_code=403, detail="Knowledge snippets not allowed for master tenants")
    
    now = datetime.now(timezone.utc).isoformat()
    snippet_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "title": snippet_data.get("title", ""),
        "content": snippet_data.get("content", ""),
        "tags": snippet_data.get("tags", []),
        "created_at": now,
        "updated_at": now
    }
    
    await db.knowledge_snippets.insert_one(snippet_doc)
    snippet_doc.pop("_id", None)
    return snippet_doc


@router.put("/{tenant_id}/knowledge-snippets/{snippet_id}")
async def update_knowledge_snippet(
    tenant_id: str,
    snippet_id: str,
    snippet_data: dict,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Update a knowledge snippet (Super Admin only)"""
    db = get_db()
    
    # Find existing snippet
    existing = await db.knowledge_snippets.find_one({"id": snippet_id, "tenant_id": tenant_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Snippet not found")
    
    update_data = {
        "title": snippet_data.get("title", existing.get("title", "")),
        "content": snippet_data.get("content", existing.get("content", "")),
        "tags": snippet_data.get("tags", existing.get("tags", [])),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.knowledge_snippets.update_one(
        {"id": snippet_id, "tenant_id": tenant_id},
        {"$set": update_data}
    )
    
    updated = await db.knowledge_snippets.find_one({"id": snippet_id}, {"_id": 0})
    return updated


@router.delete("/{tenant_id}/knowledge-snippets/{snippet_id}", status_code=204)
async def delete_knowledge_snippet(
    tenant_id: str,
    snippet_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Delete a knowledge snippet (Super Admin only)"""
    db = get_db()
    
    result = await db.knowledge_snippets.delete_one({"id": snippet_id, "tenant_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Snippet not found")
    
    return None