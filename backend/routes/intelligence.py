from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging

from models import (
    Intelligence, IntelligenceCreate, IntelligenceType,
    PaginatedResponse, PaginationMetadata
)
from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("", response_model=Intelligence)
async def create_intelligence(
    intel_data: IntelligenceCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create new intelligence item"""
    db = get_db()
    
    # Validate tenant access
    if current_user.role != "super_admin" and intel_data.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    intel_doc = {
        "id": str(uuid.uuid4()),
        **intel_data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    
    await db.intelligence.insert_one(intel_doc)
    return Intelligence(**intel_doc)

@router.get("", response_model=PaginatedResponse)
async def list_intelligence(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = Query(None),
    type: Optional[IntelligenceType] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """List intelligence items with pagination and filters"""
    db = get_db()
    
    # Build query with tenant isolation
    query = {}
    if current_user.role == "super_admin":
        if tenant_id:
            query["tenant_id"] = tenant_id
    else:
        query["tenant_id"] = current_user.tenant_id
    
    if type:
        query["type"] = type
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.intelligence.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * per_page
    cursor = db.intelligence.find(query, {"_id": 0}).skip(skip).limit(per_page).sort("created_at", -1)
    intelligence_items = await cursor.to_list(length=per_page)
    
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse(
        data=[Intelligence(**i) for i in intelligence_items],
        pagination=PaginationMetadata(
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
    )

@router.get("/{intel_id}", response_model=Intelligence)
async def get_intelligence(
    intel_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get intelligence item by ID"""
    db = get_db()
    
    intel_doc = await db.intelligence.find_one({"id": intel_id}, {"_id": 0})
    
    if not intel_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intelligence item not found"
        )
    
    # Access control
    if current_user.role != "super_admin" and intel_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return Intelligence(**intel_doc)

@router.delete("/{intel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intelligence(
    intel_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete intelligence item - tenant users can delete their own reports"""
    db = get_db()
    
    # Check exists and access control
    intel_doc = await db.intelligence.find_one({"id": intel_id})
    if not intel_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intelligence item not found"
        )
    
    if intel_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    await db.intelligence.delete_one({"id": intel_id})
    return None

@router.patch("/{intel_id}")
async def update_intelligence(
    intel_id: str,
    update_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """Update intelligence item (archive, add notes)"""
    db = get_db()
    
    intel_doc = await db.intelligence.find_one({"id": intel_id})
    if not intel_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intelligence item not found"
        )
    
    if intel_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Only allow updating client-editable fields
    allowed_fields = ["is_archived", "client_notes"]
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.intelligence.update_one(
        {"id": intel_id},
        {"$set": update_dict}
    )
    
    updated = await db.intelligence.find_one({"id": intel_id}, {"_id": 0})
    return Intelligence(**updated)