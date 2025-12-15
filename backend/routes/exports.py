from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.responses import StreamingResponse
from typing import List
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
import pandas as pd

from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("/pdf")
async def export_opportunities_pdf(
    export_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Export opportunities to branded PDF.
    Expects: {"opportunity_ids": List[str], "include_intelligence": bool}
    """
    db = get_db()
    
    opportunity_ids = export_data.get("opportunity_ids", [])
    
    # Get tenant for branding
    tenant = await db.tenants.find_one({"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Get opportunities
    opportunities = await db.opportunities.find(
        {"id": {"$in": opportunity_ids}, "tenant_id": current_user.tenant_id},
        {"_id": 0}
    ).to_list(length=len(opportunity_ids))
    
    if not opportunities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No opportunities found"
        )
    
    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a73e8'),
        spaceAfter=30
    )
    
    # Header with branding
    branding = tenant.get("branding", {})
    story.append(Paragraph(f"Opportunities Report", title_style))
    story.append(Paragraph(f"{tenant['name']}", styles['Heading2']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Add opportunities
    for opp in opportunities:
        story.append(Paragraph(f"<b>{opp['title']}</b>", styles['Heading3']))
        story.append(Paragraph(f"Score: {opp['score']}/100", styles['Normal']))
        story.append(Paragraph(f"Agency: {opp.get('agency', 'N/A')}", styles['Normal']))
        story.append(Paragraph(f"Due Date: {opp.get('due_date', 'N/A')}", styles['Normal']))
        story.append(Paragraph(f"Description: {opp['description'][:200]}...", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Powered by OutPace Intelligence", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=opportunities_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )

@router.post("/excel")
async def export_opportunities_excel(
    export_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Export opportunities to Excel.
    Expects: {"opportunity_ids": List[str]}
    """
    db = get_db()
    
    opportunity_ids = export_data.get("opportunity_ids", [])
    
    # Get opportunities
    opportunities = await db.opportunities.find(
        {"id": {"$in": opportunity_ids}, "tenant_id": current_user.tenant_id},
        {"_id": 0}
    ).to_list(length=len(opportunity_ids))
    
    if not opportunities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No opportunities found"
        )
    
    # Convert to DataFrame
    df = pd.DataFrame(opportunities)
    
    # Select and reorder columns
    columns = ['title', 'score', 'agency', 'due_date', 'estimated_value', 'description', 'source_type']
    df = df[[col for col in columns if col in df.columns]]
    
    # Create Excel file
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Opportunities', index=False)
    
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=opportunities_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )