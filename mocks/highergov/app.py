"""
HigherGov Mock Server
Port: 8002
Endpoints:
  - GET /api/opportunities
  - GET /api/opportunities/{id}
  - GET /health

Simulates government contracting opportunity API responses.
"""

import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List

app = FastAPI(title="HigherGov Mock Server", version="1.0.0")

# Mock opportunity data
MOCK_OPPORTUNITIES = [
    {
        "id": "OPP-001",
        "title": "IT Infrastructure Modernization",
        "agency": "Department of Defense",
        "posted_date": (datetime.now() - timedelta(days=5)).isoformat(),
        "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
        "value": 5000000,
        "naics_code": "541512",
        "set_aside": "Small Business",
        "status": "open",
        "description": "Modernization of legacy IT infrastructure systems."
    },
    {
        "id": "OPP-002",
        "title": "Cybersecurity Assessment Services",
        "agency": "Department of Homeland Security",
        "posted_date": (datetime.now() - timedelta(days=10)).isoformat(),
        "due_date": (datetime.now() + timedelta(days=15)).isoformat(),
        "value": 2500000,
        "naics_code": "541519",
        "set_aside": "8(a)",
        "status": "open",
        "description": "Comprehensive cybersecurity assessment and remediation."
    },
    {
        "id": "OPP-003",
        "title": "Cloud Migration Project",
        "agency": "General Services Administration",
        "posted_date": (datetime.now() - timedelta(days=20)).isoformat(),
        "due_date": (datetime.now() + timedelta(days=45)).isoformat(),
        "value": 10000000,
        "naics_code": "541512",
        "set_aside": "None",
        "status": "open",
        "description": "Migration of agency systems to cloud infrastructure."
    },
    {
        "id": "OPP-004",
        "title": "Data Analytics Platform",
        "agency": "Department of Health and Human Services",
        "posted_date": (datetime.now() - timedelta(days=3)).isoformat(),
        "due_date": (datetime.now() + timedelta(days=60)).isoformat(),
        "value": 3500000,
        "naics_code": "541511",
        "set_aside": "WOSB",
        "status": "open",
        "description": "Development of enterprise data analytics platform."
    },
    {
        "id": "OPP-005",
        "title": "Network Security Upgrade",
        "agency": "Department of Veterans Affairs",
        "posted_date": (datetime.now() - timedelta(days=7)).isoformat(),
        "due_date": (datetime.now() + timedelta(days=25)).isoformat(),
        "value": 1800000,
        "naics_code": "541519",
        "set_aside": "SDVOSB",
        "status": "open",
        "description": "Upgrade of network security infrastructure."
    }
]


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "highergov-mock", "port": 8002}


@app.get("/api/opportunities")
async def list_opportunities(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    agency: Optional[str] = None,
    naics_code: Optional[str] = None,
    set_aside: Optional[str] = None,
    status: Optional[str] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    search: Optional[str] = None
):
    """List opportunities with filtering and pagination."""
    filtered = MOCK_OPPORTUNITIES.copy()

    # Apply filters
    if agency:
        filtered = [o for o in filtered if agency.lower() in o["agency"].lower()]

    if naics_code:
        filtered = [o for o in filtered if o["naics_code"] == naics_code]

    if set_aside:
        filtered = [o for o in filtered if set_aside.lower() in o["set_aside"].lower()]

    if status:
        filtered = [o for o in filtered if o["status"] == status]

    if min_value is not None:
        filtered = [o for o in filtered if o["value"] >= min_value]

    if max_value is not None:
        filtered = [o for o in filtered if o["value"] <= max_value]

    if search:
        search_lower = search.lower()
        filtered = [o for o in filtered if
                   search_lower in o["title"].lower() or
                   search_lower in o["description"].lower()]

    # Pagination
    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = filtered[start:end]

    return {
        "data": paginated,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0
        }
    }


@app.get("/api/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: str):
    """Get a specific opportunity by ID."""
    for opp in MOCK_OPPORTUNITIES:
        if opp["id"] == opportunity_id:
            # Return full details
            return {
                **opp,
                "attachments": [
                    {"name": "RFP_Document.pdf", "size": 1024000, "url": f"/attachments/{opportunity_id}/rfp.pdf"},
                    {"name": "Requirements.xlsx", "size": 51200, "url": f"/attachments/{opportunity_id}/requirements.xlsx"}
                ],
                "contacts": [
                    {"name": "John Smith", "email": "john.smith@agency.gov", "phone": "202-555-0100"}
                ],
                "amendments": []
            }

    raise HTTPException(status_code=404, detail=f"Opportunity {opportunity_id} not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
