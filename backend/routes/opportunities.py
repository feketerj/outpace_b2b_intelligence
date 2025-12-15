from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging

from models import (
    Opportunity, OpportunityCreate, OpportunitySource,
    PaginatedResponse, PaginationMetadata
)
from utils.auth import get_current_user, TokenData
from utils.scoring import calculate_opportunity_score
from database import get_database

def get_db():
    return get_database()

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=Opportunity)
async def create_opportunity(
    opp_data: OpportunityCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create new opportunity (manual upload)"""
    db = get_db()
    
    # Validate tenant access
    if current_user.role != "super_admin" and opp_data.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check for duplicate
    existing = await db.opportunities.find_one({
        "tenant_id": opp_data.tenant_id,
        "external_id": opp_data.external_id
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opportunity already exists"
        )
    
    # Get tenant's scoring weights
    tenant = await db.tenants.find_one({"id": opp_data.tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    weights = tenant.get("scoring_weights", {})
    
    # Calculate score
    opp_dict = opp_data.model_dump()
    score = calculate_opportunity_score(opp_dict, weights)
    
    now = datetime.now(timezone.utc).isoformat()
    opp_doc = {
        "id": str(uuid.uuid4()),
        **opp_dict,
        "score": score,
        "ai_relevance_summary": None,
        "captured_date": now,
        "created_at": now,
        "updated_at": now
    }
    
    await db.opportunities.insert_one(opp_doc)
    return Opportunity(**opp_doc)

@router.get("", response_model=PaginatedResponse)
async def list_opportunities(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = Query(None),
    source_type: Optional[OpportunitySource] = None,
    min_score: Optional[int] = Query(None, ge=0, le=100),
    search: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """List opportunities with pagination and filters"""
    db = get_db()
    
    # Build query with tenant isolation
    query = {}
    if current_user.role == "super_admin":
        if tenant_id:
            query["tenant_id"] = tenant_id
    else:
        query["tenant_id"] = current_user.tenant_id
    
    if source_type:
        query["source_type"] = source_type
    if min_score is not None:
        query["score"] = {"$gte": min_score}
    if search:
        query["$text"] = {"$search": search}
    
    # Get total count
    total = await db.opportunities.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * per_page
    cursor = db.opportunities.find(query, {"_id": 0}).skip(skip).limit(per_page).sort("score", -1)
    opportunities = await cursor.to_list(length=per_page)
    
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse(
        data=[Opportunity(**o) for o in opportunities],
        pagination=PaginationMetadata(
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
    )

@router.get("/{opp_id}", response_model=Opportunity)
async def get_opportunity(
    opp_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get opportunity by ID"""
    db = get_db()
    
    opp_doc = await db.opportunities.find_one({"id": opp_id}, {"_id": 0})
    
    if not opp_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found"
        )
    
    # Access control
    if current_user.role != "super_admin" and opp_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return Opportunity(**opp_doc)

@router.delete("/{opp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opp_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete opportunity"""
    db = get_db()
    
    # Check exists and access control
    opp_doc = await db.opportunities.find_one({"id": opp_id})
    if not opp_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found"
        )
    
    if current_user.role != "super_admin" and opp_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    await db.opportunities.delete_one({"id": opp_id})
    return None

@router.get("/stats/{tenant_id}")
async def get_opportunity_stats(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get opportunity statistics for tenant"""
    db = get_db()
    
    # Access control
    if current_user.role != "super_admin" and tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get counts and stats
    total = await db.opportunities.count_documents({"tenant_id": tenant_id})
    high_score = await db.opportunities.count_documents({"tenant_id": tenant_id, "score": {"$gte": 75}})
    
    # Get source breakdown
    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {"_id": "$source_type", "count": {"$sum": 1}}}
    ]
    source_breakdown = await db.opportunities.aggregate(pipeline).to_list(None)
    
    return {
        "total": total,
        "high_score_count": high_score,
        "source_breakdown": {item["_id"]: item["count"] for item in source_breakdown}
    }