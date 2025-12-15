from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging

from models import User, UserCreate, UserUpdate, UserRole, PaginatedResponse, PaginationMetadata
from utils.auth import get_current_tenant_admin, get_current_user, get_password_hash, TokenData
from database import get_database

def get_db():
    return get_database()

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=User)
async def create_user(
    user_data: UserCreate,
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """Create new user"""
    db = get_db()
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Tenant admins can only create users for their own tenant
    if current_user.role == UserRole.TENANT_ADMIN:
        if not user_data.tenant_id or user_data.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only create users for your own tenant"
            )
        if user_data.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create super admin users"
            )
    
    # Validate tenant exists
    if user_data.tenant_id:
        tenant = await db.tenants.find_one({"id": user_data.tenant_id})
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
    
    now = datetime.now(timezone.utc).isoformat()
    user_doc = {
        "id": str(uuid.uuid4()),
        "email": user_data.email,
        "full_name": user_data.full_name,
        "role": user_data.role,
        "tenant_id": user_data.tenant_id,
        "hashed_password": get_password_hash(user_data.password),
        "created_at": now,
        "updated_at": now,
        "last_login": None
    }
    
    await db.users.insert_one(user_doc)
    
    return User(**{k: v for k, v in user_doc.items() if k != "hashed_password"})

@router.get("", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = None,
    role: Optional[UserRole] = None,
    search: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user)
):
    """List users with pagination"""
    db = get_db()
    
    # Build query
    query = {}
    
    # Access control
    if current_user.role == UserRole.TENANT_ADMIN:
        query["tenant_id"] = current_user.tenant_id
    elif current_user.role == UserRole.TENANT_USER:
        query["tenant_id"] = current_user.tenant_id
    elif tenant_id:
        query["tenant_id"] = tenant_id
    
    if role:
        query["role"] = role
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count
    total = await db.users.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * per_page
    cursor = db.users.find(query, {"_id": 0, "hashed_password": 0}).skip(skip).limit(per_page).sort("created_at", -1)
    users = await cursor.to_list(length=per_page)
    
    pages = (total + per_page - 1) // per_page
    
    return PaginatedResponse(
        data=[User(**u) for u in users],
        pagination=PaginationMetadata(
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
    )

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str, current_user: TokenData = Depends(get_current_user)):
    """Get user by ID"""
    db = get_db()
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Access control
    if current_user.role == UserRole.TENANT_ADMIN and user_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return User(**user_doc)

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """Update user"""
    db = get_db()
    
    # Check user exists
    existing_user = await db.users.find_one({"id": user_id})
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Access control
    if current_user.role == UserRole.TENANT_ADMIN and existing_user.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Update user
    update_data = {k: v for k, v in user_data.model_dump(exclude_unset=True).items() if v is not None}
    
    # Hash password if updating
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    # Return updated user
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    return User(**updated_user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """Delete user"""
    db = get_db()
    
    # Check user exists
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Access control
    if current_user.role == UserRole.TENANT_ADMIN and user_doc.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Prevent deleting yourself
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    await db.users.delete_one({"id": user_id})
    return None