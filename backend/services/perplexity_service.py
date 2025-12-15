import httpx
import logging
import os
from datetime import datetime, timezone, timedelta
import uuid
from typing import Dict, Any

logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

async def sync_perplexity_intelligence(db, tenant: dict) -> int:
    """
    Generate intelligence reports using Perplexity API for a tenant.
    Uses configurable prompt template and schedule.
    Returns number of new intelligence items added.
    """
    tenant_id = tenant["id"]
    tenant_name = tenant["name"]
    
    # Get intelligence configuration
    intel_config = tenant.get("intelligence_config", {})
    
    if not intel_config.get("enabled", True):
        logger.info(f"Intelligence generation disabled for tenant {tenant_id}")
        return 0
    
    # Get search profile for context
    search_profile = tenant.get("search_profile", {})
    competitors = search_profile.get("competitors", [])
    interest_areas = search_profile.get("interest_areas", [])
    naics_codes = search_profile.get("naics_codes", [])
    keywords = search_profile.get("keywords", [])
    
    # Check if placeholder key
    if not PERPLEXITY_API_KEY or "placeholder" in PERPLEXITY_API_KEY.lower():
        logger.warning("Perplexity API key not configured, skipping sync")
        return 0
    
    new_count = 0
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Use custom prompt template if provided, otherwise use default
            prompt_template = intel_config.get("perplexity_prompt_template")
            
            if prompt_template:
                # Replace template variables
                lookback_days = intel_config.get("lookback_days", 14)
                deadline_window = intel_config.get("deadline_window_days", 120)
                
                prompt = prompt_template.replace("{{COMPANY_NAME}}", tenant_name)
                prompt = prompt.replace("{{LOOKBACK_DAYS}}", str(lookback_days))
                prompt = prompt.replace("{{DEADLINE_WINDOW}}", str(deadline_window))
                prompt = prompt.replace("{{COMPETITORS}}", ", ".join(competitors))
                prompt = prompt.replace("{{INTEREST_AREAS}}", ", ".join(interest_areas))
                prompt = prompt.replace("{{NAICS_CODES}}", ", ".join(naics_codes))
                prompt = prompt.replace("{{KEYWORDS}}", ", ".join(keywords))
                prompt = prompt.replace("{{CURRENT_DATE}}", datetime.now().strftime("%Y-%m-%d"))
                
                # Single comprehensive query with the full template
                queries = [prompt]
            else:
                # Fallback to simple queries if no template
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
                                    "content": "You are a business intelligence analyst and Washington K Street operator. Provide structured, actionable intelligence reports with official sources and absolute dates."
                                },
                                {
                                    "role": "user",
                                    "content": query
                                }
                            ],
                            "temperature": 0.3,
                            "max_tokens": 4000,  # Increased for comprehensive reports
                            "search_recency_filter": "week"  # Focus on recent data
                        }
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    citations = result.get("citations", [])
                    
                    # Determine title based on whether custom template was used
                    if prompt_template:
                        title = f"{tenant_name} - Intelligence Report - {datetime.now().strftime('%Y-%m-%d')}"
                        intel_type = "custom_report"
                    else:
                        title = query[:100]
                        intel_type = "news"
                    
                    # Create intelligence item
                    now = datetime.now(timezone.utc).isoformat()
                    intelligence = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "title": title,
                        "summary": content[:500],
                        "content": content,
                        "type": intel_type,
                        "source_urls": citations,
                        "keywords": competitors + interest_areas + keywords,
                        "metadata": {
                            "query": query[:200],  # Store truncated query
                            "model": "sonar-pro",
                            "lookback_days": intel_config.get("lookback_days", 14),
                            "has_custom_template": bool(prompt_template)
                        },
                        "created_at": now,
                        "updated_at": now
                    }
                    
                    await db.intelligence.insert_one(intelligence)
                    new_count += 1
                    
                    logger.info(f"Generated intelligence report for {tenant_name}: {title}")
                    
                except Exception as e:
                    logger.error(f"Error querying Perplexity: {e}")
                    continue
            
    except Exception as e:
        logger.error(f"Perplexity API error for tenant {tenant_id}: {e}")
        raise
    
    return new_count