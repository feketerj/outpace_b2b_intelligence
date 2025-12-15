import httpx
import logging
import os
from datetime import datetime, timezone
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

async def sync_perplexity_intelligence(db, tenant: dict) -> int:
    """
    Generate intelligence reports using Perplexity API for a tenant.
    Returns number of new intelligence items added.
    """
    tenant_id = tenant["id"]
    search_profile = tenant.get("search_profile", {})
    competitors = search_profile.get("competitors", [])
    interest_areas = search_profile.get("interest_areas", [])
    
    if not competitors and not interest_areas:
        logger.warning(f"No intelligence search criteria for tenant {tenant_id}")
        return 0
    
    # Check if placeholder key
    if not PERPLEXITY_API_KEY or "placeholder" in PERPLEXITY_API_KEY.lower():
        logger.warning("Perplexity API key not configured, skipping sync")
        return 0
    
    new_count = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Generate queries for intelligence
            queries = []
            
            if competitors:
                comp_list = ", ".join(competitors[:3])
                queries.append(f"Latest news and developments about {comp_list} in the past week")
            
            if interest_areas:
                area_list = ", ".join(interest_areas[:2])
                queries.append(f"Recent market trends and analysis in {area_list}")
            
            # Query Perplexity for each topic
            for query in queries:
                try:
                    response = await client.post(
                        f"{PERPLEXITY_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "sonar-pro",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a business intelligence analyst. Provide concise, factual summaries with sources."
                                },
                                {
                                    "role": "user",
                                    "content": query
                                }
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1000
                        }
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    citations = result.get("citations", [])
                    
                    # Create intelligence item
                    now = datetime.now(timezone.utc).isoformat()
                    intelligence = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "title": query[:100],
                        "summary": content[:500],
                        "content": content,
                        "type": "news",
                        "source_urls": citations,
                        "keywords": competitors + interest_areas,
                        "metadata": {
                            "query": query,
                            "model": "sonar-pro"
                        },
                        "created_at": now,
                        "updated_at": now
                    }
                    
                    await db.intelligence.insert_one(intelligence)
                    new_count += 1
                    
                except Exception as e:
                    logger.error(f"Error querying Perplexity: {e}")
                    continue
            
    except Exception as e:
        logger.error(f"Perplexity API error for tenant {tenant_id}: {e}")
        raise
    
    return new_count