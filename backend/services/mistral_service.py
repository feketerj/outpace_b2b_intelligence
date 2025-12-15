import httpx
import logging
import os
from datetime import datetime, timezone
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("EMERGENT_LLM_KEY")
MISTRAL_BASE_URL = "https://api.mistral.ai/v1/agents/completions"

async def score_opportunity_with_ai(opportunity: dict, tenant: dict) -> Dict[str, Any]:
    """
    Use Mistral scoring agent to analyze and score an opportunity.
    Returns: {"relevance_summary": str, "suggested_score_adjustment": int}
    """
    # Get scoring agent ID
    agent_config = tenant.get("agent_config", {})
    agent_id = agent_config.get("pre_display_agent_id") or os.getenv("DEFAULT_SCORING_AGENT_ID")
    
    # Check if keys are configured
    if not MISTRAL_API_KEY or "placeholder" in MISTRAL_API_KEY.lower():
        logger.warning("Mistral API key not configured, skipping AI scoring")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}
    
    try:
        # Prepare prompt
        prompt = f"""
Analyze this contract opportunity and provide:
1. A concise relevance summary (2-3 sentences)
2. A score adjustment recommendation (-20 to +20)

Opportunity:
Title: {opportunity.get('title', '')}
Agency: {opportunity.get('agency', '')}
Description: {opportunity.get('description', '')[:500]}
Estimated Value: {opportunity.get('estimated_value', 'N/A')}

Tenant Profile:
Interest Areas: {', '.join(tenant.get('search_profile', {}).get('interest_areas', []))}
Competitors: {', '.join(tenant.get('search_profile', {}).get('competitors', []))}

Respond in JSON format:
{{
  "relevance_summary": "...",
  "score_adjustment": 0
}}
"""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                MISTRAL_BASE_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {MISTRAL_API_KEY}"
                },
                json={
                    "agent_id": agent_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            
            # Parse JSON response
            try:
                parsed = json.loads(content)
                return {
                    "relevance_summary": parsed.get("relevance_summary"),
                    "suggested_score_adjustment": parsed.get("score_adjustment", 0)
                }
            except:
                return {
                    "relevance_summary": content,
                    "suggested_score_adjustment": 0
                }
    
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}