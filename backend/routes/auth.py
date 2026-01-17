from fastapi import APIRouter, HTTPException, status, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone, timedelta
import os
import logging
import uuid

from backend.models import (
    LoginRequest, Token, User, UserCreate, UserInDB, UserRole,
    RefreshTokenRequest, RefreshTokenResponse
)
from backend.utils.auth import (
    verify_password, get_password_hash, create_access_token, get_current_user,
    validate_password_policy, create_refresh_token_jwt, decode_refresh_token,
    hash_refresh_token, JWT_EXPIRATION_HOURS, JWT_REFRESH_EXPIRATION_DAYS
)
from backend.database import get_database
from backend.utils.rate_limit import limiter, AUTH_RATE_LIMIT

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()


async def _store_refresh_token(db, user_id: str, token_hash: str, expires_at: datetime) -> str:
    """Store a refresh token hash in the database."""
    token_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.refresh_tokens.insert_one({
        "id": token_id,
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": expires_at.isoformat(),
        "created_at": now,
        "revoked": False,
        "revoked_at": None
    })
    return token_id


async def _revoke_refresh_token(db, token_hash: str) -> bool:
    """Revoke a refresh token by its hash."""
    result = await db.refresh_tokens.update_one(
        {"token_hash": token_hash, "revoked": False},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    return result.modified_count > 0


async def _is_refresh_token_valid(db, token_hash: str) -> bool:
    """Check if a refresh token is valid (exists, not revoked, not expired)."""
    token_doc = await db.refresh_tokens.find_one({"token_hash": token_hash})
    if not token_doc:
        return False
    if token_doc.get("revoked"):
        return False
    expires_at = datetime.fromisoformat(token_doc["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        return False
    return True


async def _revoke_all_user_tokens(db, user_id: str) -> int:
    """Revoke all refresh tokens for a user (logout from all devices)."""
    result = await db.refresh_tokens.update_many(
        {"user_id": user_id, "revoked": False},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    return result.modified_count


@router.post("/login", response_model=Token)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, login_data: LoginRequest):
    """Authenticate user and return JWT access token + refresh token"""
    db = get_db()
    
    # Find user by email
    user_doc = await db.users.find_one({"email": login_data.email}, {"_id": 0})
    
    if not user_doc or not verify_password(login_data.password, user_doc.get("hashed_password", "")):
        logger.warning(f"[audit.login_failed] email={login_data.email} reason={'user_not_found' if not user_doc else 'bad_password'}")
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
    access_token, access_expires = create_access_token(token_data)
    
    # Create refresh token
    refresh_token, refresh_expires = create_refresh_token_jwt({"sub": user_doc["id"]})
    
    # Store refresh token hash in database
    await _store_refresh_token(db, user_doc["id"], hash_refresh_token(refresh_token), refresh_expires)
    
    # Calculate expires_in (seconds until access token expires)
    expires_in = int((access_expires - datetime.now(timezone.utc)).total_seconds())
    
    # Convert to User model
    user = User(**{k: v for k, v in user_doc.items() if k != "hashed_password"})
    
    logger.info(f"[audit.login_success] user_id={user_doc['id']} email={user_doc['email']} role={user_doc['role']}")
    return Token(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        user=user
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh_token(request: Request, refresh_data: RefreshTokenRequest):
    """
    Exchange a valid refresh token for a new access token.
    
    Implements token rotation: the old refresh token is revoked and a new one is NOT issued.
    Client must use the original refresh token until it expires, then re-login.
    """
    db = get_db()
    
    # Decode and validate the refresh token JWT
    token_payload = decode_refresh_token(refresh_data.refresh_token)
    user_id = token_payload["user_id"]
    
    # Check if token hash is in our database and not revoked
    token_hash = hash_refresh_token(refresh_data.refresh_token)
    if not await _is_refresh_token_valid(db, token_hash):
        logger.warning(f"[audit.refresh_failed] user_id={user_id} reason=token_revoked_or_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or is invalid"
        )
    
    # Get user data
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        logger.warning(f"[audit.refresh_failed] user_id={user_id} reason=user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new access token
    token_data = {
        "sub": user_doc["id"],
        "email": user_doc["email"],
        "role": user_doc["role"],
        "tenant_id": user_doc.get("tenant_id")
    }
    access_token, access_expires = create_access_token(token_data)
    
    # Calculate expires_in
    expires_in = int((access_expires - datetime.now(timezone.utc)).total_seconds())
    
    logger.info(f"[audit.token_refreshed] user_id={user_id}")
    return RefreshTokenResponse(
        access_token=access_token,
        expires_in=expires_in
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(AUTH_RATE_LIMIT)
async def logout(request: Request, refresh_data: RefreshTokenRequest):
    """
    Logout by revoking the provided refresh token.
    
    After logout, the refresh token cannot be used to obtain new access tokens.
    The access token remains valid until it expires (stateless JWT).
    """
    db = get_db()
    
    try:
        token_payload = decode_refresh_token(refresh_data.refresh_token)
        user_id = token_payload["user_id"]
    except HTTPException:
        # Token already invalid - that's fine for logout
        return None
    
    token_hash = hash_refresh_token(refresh_data.refresh_token)
    revoked = await _revoke_refresh_token(db, token_hash)
    
    if revoked:
        logger.info(f"[audit.logout] user_id={user_id}")
    
    return None


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user=Depends(get_current_user)):
    """
    Logout from all devices by revoking all refresh tokens for the current user.
    
    Requires a valid access token. After this, all refresh tokens are invalidated.
    """
    db = get_db()
    
    count = await _revoke_all_user_tokens(db, current_user.user_id)
    logger.info(f"[audit.logout_all] user_id={current_user.user_id} tokens_revoked={count}")
    
    return None


@router.post("/register", response_model=User)
@limiter.limit(AUTH_RATE_LIMIT)
async def register(request: Request, user_data: UserCreate):
    """Register new user (super admin or tenant user)"""
    db = get_db()
    
    # Validate password policy
    is_valid, errors = validate_password_policy(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password does not meet requirements", "errors": errors}
        )
    
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
    
    logger.info(f"[audit.user_registered] user_id={user_doc['id']} email={user_doc['email']}")
    
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