from fastapi import APIRouter, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
import os
import logging

from backend.models import LoginRequest, Token, User, UserCreate, UserInDB, UserRole
from backend.utils.auth import verify_password, get_password_hash, create_access_token, get_current_user
from backend.database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """Authenticate user and return JWT token"""
    db = get_db()
    
    # Find user by email
    user_doc = await db.users.find_one({"email": login_data.email}, {"_id": 0})
    
    if not user_doc or not verify_password(login_data.password, user_doc.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Update last login
    await db.users.update_one(
        {"email": login_data.email},
        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Create access token
    token_data = {
        "sub": user_doc["id"],
        "email": user_doc["email"],
        "role": user_doc["role"],
        "tenant_id": user_doc.get("tenant_id")
    }
    access_token = create_access_token(token_data)
    
    # Convert to User model
    user = User(**{k: v for k, v in user_doc.items() if k != "hashed_password"})
    
    return Token(access_token=access_token, user=user)

@router.post("/register", response_model=User)
async def register(user_data: UserCreate):
    """Register new user (super admin or tenant user)"""
    db = get_db()
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate tenant exists if tenant_id provided
    if user_data.tenant_id:
        tenant = await db.tenants.find_one({"id": user_data.tenant_id})
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
    
    # Create user
    import uuid
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
    
    # Return user without password
    return User(**{k: v for k, v in user_doc.items() if k != "hashed_password"})

@router.get("/me", response_model=User)
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information"""
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.user_id}, {"_id": 0, "hashed_password": 0})
    
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return User(**user_doc)