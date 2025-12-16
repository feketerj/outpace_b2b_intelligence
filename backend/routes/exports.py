from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.responses import StreamingResponse
from typing import List
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import pandas as pd
import base64
from PIL import Image as PILImage
import openpyxl.styles

from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("/pdf")
async def export_branded_pdf(
    export_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Export opportunities and intelligence to BRANDED PDF with client logo and colors.
    Includes master client branding if applicable.
    """
    db = get_db()
    
    opportunity_ids = export_data.get("opportunity_ids", [])
    intelligence_ids = export_data.get("intelligence_ids", [])
    
    # Get tenant for branding
    tenant = await db.tenants.find_one({"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Use master branding if this is a sub-client, otherwise use tenant branding
    effective_branding = tenant.get("master_branding") or tenant.get("branding", {})
    master_name = tenant.get("master_client_name") if tenant.get("master_client_id") else None
    
    # Get data
    opportunities = []
    intelligence_items = []
    
    if opportunity_ids:
        cursor = db.opportunities.find({"id": {"$in": opportunity_ids}, "tenant_id": current_user.tenant_id}, {"_id": 0})
        opportunities = await cursor.to_list(length=len(opportunity_ids))
    
    if intelligence_ids:
        cursor = db.intelligence.find({"id": {"$in": intelligence_ids}, "tenant_id": current_user.tenant_id}, {"_id": 0})
        intelligence_items = await cursor.to_list(length=len(intelligence_ids))
    
    if not opportunities and not intelligence_items:
        raise HTTPException(status_code=404, detail="No data to export")
    
    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Get brand colors
    primary_color_str = effective_branding.get("primary_color", "hsl(210, 85%, 52%)")
    # Convert HSL to hex (simple approximation for blue)
    primary_hex = "#1a73e8"  # Default blue
    
    # Custom styles with branding
    title_style = ParagraphStyle(
        'BrandedTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor(primary_hex),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'BrandedHeader',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor(primary_hex),
        spaceAfter=15
    )
    
    # Logo (if available)
    logo_data = effective_branding.get("logo_base64") or effective_branding.get("logo_url")
    if logo_data and logo_data.startswith('data:image'):
        try:
            # Extract base64 data
            img_data = logo_data.split(',')[1]
            img_bytes = base64.b64decode(img_data)
            img = PILImage.open(io.BytesIO(img_bytes))
            
            # Add logo to PDF (top center)
            from reportlab.platypus import Image as RLImage
            logo_img = RLImage(io.BytesIO(img_bytes), width=2*inch, height=0.5*inch, kind='proportional')
            story.append(logo_img)
            story.append(Spacer(1, 0.2*inch))
        except Exception as e:
            logger.error(f"Failed to add logo: {e}")
    
    # Title
    story.append(Paragraph(f"{tenant['name']} - Intelligence Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Opportunities Section
    if opportunities:
        story.append(Paragraph("Contract Opportunities", header_style))
        story.append(Spacer(1, 0.1*inch))
        
        for opp in opportunities:
            story.append(Paragraph(f"<b>{opp['title']}</b>", styles['Heading3']))
            story.append(Paragraph(f"Score: {opp['score']}/100 | Agency: {opp.get('agency', 'N/A')}", styles['Normal']))
            story.append(Paragraph(f"Due Date: {opp.get('due_date', 'N/A')}", styles['Normal']))
            story.append(Paragraph(f"Estimated Value: {opp.get('estimated_value', 'N/A')}", styles['Normal']))
            
            if opp.get('ai_relevance_summary'):
                story.append(Paragraph(f"<i>AI Analysis: {opp['ai_relevance_summary']}</i>", styles['Normal']))
            
            story.append(Paragraph(f"Description: {opp['description'][:300]}...", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
    
    # Intelligence Section
    if intelligence_items:
        if opportunities:
            story.append(PageBreak())
        
        story.append(Paragraph("Business Intelligence Reports", header_style))
        story.append(Spacer(1, 0.1*inch))
        
        for item in intelligence_items:
            story.append(Paragraph(f"<b>{item['title']}</b>", styles['Heading3']))
            story.append(Paragraph(f"Date: {datetime.fromisoformat(item['created_at']).strftime('%B %d, %Y')}", styles['Normal']))
            story.append(Paragraph(item['content'][:500] + '...', styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    powered_by = f"Powered by {master_name}" if master_name else "Powered by OutPace Intelligence"
    story.append(Paragraph(powered_by, styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={tenant['slug']}_export_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )

@router.post("/excel")
async def export_branded_excel(
    export_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """Export to Excel with branded header"""
    db = get_db()
    
    opportunity_ids = export_data.get("opportunity_ids", [])
    intelligence_ids = export_data.get("intelligence_ids", [])
    
    tenant = await db.tenants.find_one({"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    buffer = io.BytesIO()
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Opportunities sheet
        if opportunity_ids:
            opps = await db.opportunities.find({"id": {"$in": opportunity_ids}}, {"_id": 0}).to_list(100)
            if opps:
                df = pd.DataFrame(opps)
                cols = ['title', 'score', 'agency', 'due_date', 'estimated_value', 'client_status', 'client_notes']
                df = df[[col for col in cols if col in df.columns]]
                df.to_excel(writer, sheet_name='Opportunities', index=False, startrow=2)
                
                # Add header with tenant name
                worksheet = writer.sheets['Opportunities']
                worksheet['A1'] = tenant['name']
                worksheet['A1'].font = openpyxl.styles.Font(bold=True, size=14)
        
        # Intelligence sheet
        if intelligence_ids:
            intel = await db.intelligence.find({"id": {"$in": intelligence_ids}}, {"_id": 0}).to_list(100)
            if intel:
                df = pd.DataFrame(intel)
                cols = ['title', 'type', 'summary', 'created_at']
                df = df[[col for col in cols if col in df.columns]]
                df.to_excel(writer, sheet_name='Intelligence', index=False, startrow=2)
                
                worksheet = writer.sheets['Intelligence']
                worksheet['A1'] = tenant['name']
                worksheet['A1'].font = openpyxl.styles.Font(bold=True, size=14)
    
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={tenant['slug']}_export_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )