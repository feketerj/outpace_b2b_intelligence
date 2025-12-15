from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
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
    
    # Check permissions
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
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

@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    tenant_data: TenantUpdate,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Update tenant (Super Admin only)"""
    db = get_db()
    
    # Check tenant exists
    existing_tenant = await db.tenants.find_one({"id": tenant_id})
    if not existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check slug uniqueness if updating
    if tenant_data.slug and tenant_data.slug != existing_tenant.get("slug"):
        slug_exists = await db.tenants.find_one({"slug": tenant_data.slug})
        if slug_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant slug already exists"
            )
    
    # Update tenant
    update_data = {k: v for k, v in tenant_data.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": update_data}
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
    
    return None