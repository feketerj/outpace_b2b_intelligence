from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Request
from typing import Optional
import base64
import logging
from PIL import Image
import io
import pandas as pd
import uuid
from datetime import datetime, timezone
import csv

from backend.utils.auth import get_current_tenant_admin, get_current_user, TokenData
from backend.database import get_database
from backend.utils.rate_limit import limiter, UPLOAD_RATE_LIMIT

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

def _sanitize_value(value):
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception as e:
        logger.warning(f"[upload.sanitize] pd.isna() failed for value type {type(value).__name__}: {e}")
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception as e:
            logger.warning(f"[upload.sanitize] value.item() failed for type {type(value).__name__}: {e}")
    return value

def _sanitize_record(record: dict) -> dict:
    return {k: _sanitize_value(v) for k, v in record.items()}


def _validate_csv_bytes(contents: bytes) -> None:
    if b"\x00" in contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV content (binary data detected)"
        )
    try:
        sample = contents[:4096].decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV encoding (expected UTF-8)"
        )
    try:
        csv.Sniffer().sniff(sample)
    except csv.Error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV structure"
        )

@router.post("/opportunities/csv/{tenant_id}")
@limiter.limit(UPLOAD_RATE_LIMIT)
async def upload_opportunities_csv(
    request: Request,
    tenant_id: str,
    current_user: TokenData = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """
    Upload opportunities from CSV file. Super admin only.
    CSV columns: title, description, agency, due_date, estimated_value, naics_code, source_url
    """
    db = get_db()
    
    # Access control - super admin only
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    
    # Validate file type - extension AND MIME type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be CSV format"
        )

    # Validate MIME type (security: prevent disguised files)
    allowed_csv_mimes = ['text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel']
    if file.content_type and file.content_type not in allowed_csv_mimes:
        logger.warning(f"[upload.csv] Rejected file with MIME type: {file.content_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Expected CSV."
        )

    try:
        # Read CSV
        contents = await file.read()
        _validate_csv_bytes(contents)
        df = pd.read_csv(io.BytesIO(contents))
        
        # Get tenant for scoring
        tenant = await db.tenants.find_one({"id": tenant_id})
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        weights = tenant.get("scoring_weights", {})
        imported_count = 0
        
        # Process each row
        for _, row in df.iterrows():
            now = datetime.now(timezone.utc).isoformat()
            external_id = f"manual-{uuid.uuid4()}"
            
            opportunity = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "external_id": external_id,
                "title": str(row.get("title", "Untitled")),
                "description": str(row.get("description", "")),
                "agency": str(row.get("agency", "")) if pd.notna(row.get("agency")) else None,
                "due_date": str(row.get("due_date")) if pd.notna(row.get("due_date")) else None,
                "estimated_value": str(row.get("estimated_value")) if pd.notna(row.get("estimated_value")) else None,
                "naics_code": str(row.get("naics_code")) if pd.notna(row.get("naics_code")) else None,
                "keywords": [],
                "source_type": "manual",
                "source_url": str(row.get("source_url")) if pd.notna(row.get("source_url")) else "",
                "raw_data": _sanitize_record(row.to_dict()),
                "score": 0,
                "ai_relevance_summary": None,
                "captured_date": now,
                "created_at": now,
                "updated_at": now,
                "client_status": "new",
                "client_notes": None,
                "client_tags": [],
                "is_archived": False
            }
            
            # Calculate score
            from backend.utils.scoring import calculate_opportunity_score
            opportunity["score"] = calculate_opportunity_score(opportunity, weights)
            
            await db.opportunities.insert_one(opportunity)
            imported_count += 1

        logger.info(f"[audit.csv_import] tenant_id={tenant_id} rows={imported_count} filename={file.filename} by={current_user.user_id}")
        return {
            "status": "success",
            "imported_count": imported_count,
            "total_rows": len(df)
        }
        
    except Exception as e:
        logger.error(f"CSV upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV: {str(e)}"
        )

@router.post("/logo/{tenant_id}")
@limiter.limit(UPLOAD_RATE_LIMIT)
async def upload_tenant_logo(
    request: Request,
    tenant_id: str,
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """
    Upload tenant logo. Returns base64 encoded image.
    Accepts: PNG, JPG, JPEG, SVG
    """
    db = get_db()
    
    # Access control
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate file type
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPG, JPEG, SVG"
        )
    
    # Read file
    contents = await file.read()
    
    # Validate file size (max 5MB)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum 5MB"
        )
    
    # Resize image if too large (except SVG)
    resize_failed = False
    if file.content_type != 'image/svg+xml':
        try:
            img = Image.open(io.BytesIO(contents))

            # Resize if larger than 500px
            max_size = 500
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Convert back to bytes
                output = io.BytesIO()
                img_format = 'PNG' if file.content_type == 'image/png' else 'JPEG'
                img.save(output, format=img_format)
                contents = output.getvalue()
                logger.info(f"[upload.logo] Resized to {img.width}x{img.height}")
        except Exception as e:
            logger.error(f"[upload.logo] RESIZE_FAILED: {e} - returning original image")
            resize_failed = True
    
    # Encode to base64
    logo_base64 = base64.b64encode(contents).decode('utf-8')
    logo_data_uri = f"data:{file.content_type};base64,{logo_base64}"
    
    # Update tenant branding
    result = await db.tenants.update_one(
        {"id": tenant_id},
        {
            "$set": {
                "branding.logo_base64": logo_data_uri,
                "branding.logo_url": None  # Clear URL when uploading file
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    response = {
        "status": "success",
        "logo_data_uri": logo_data_uri,
        "size_kb": len(contents) / 1024
    }
    if resize_failed:
        response["warning"] = "Image resize failed - original size used"
    return response
