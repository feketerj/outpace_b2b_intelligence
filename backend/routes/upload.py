from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from typing import Optional
import base64
import logging
from PIL import Image
import io

from utils.auth import get_current_tenant_admin, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("/logo/{tenant_id}")
async def upload_tenant_logo(
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
                logger.info(f"Resized logo to {img.width}x{img.height}")
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
    
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
    
    return {
        "status": "success",
        "logo_data_uri": logo_data_uri,
        "size_kb": len(contents) / 1024
    }
