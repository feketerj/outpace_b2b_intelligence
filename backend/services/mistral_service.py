import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any
from mistralai import Mistral

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("EMERGENT_LLM_KEY")

async def score_opportunity_with_ai(opportunity: dict, tenant: dict) -> Dict[str, Any]:
    """
    Use Mistral agent to analyze and score an opportunity.
    Supports both Agent ID (pre-created) OR dynamic instructions.
    Returns: {"relevance_summary": str, "suggested_score_adjustment": int}
    """
    agent_config = tenant.get("agent_config", {})
    agent_id = agent_config.get("scoring_agent_id")
    instructions = agent_config.get("scoring_instructions", "Analyze this contract opportunity.")
    
    # Check if keys are configured
    if not MISTRAL_API_KEY or "placeholder" in MISTRAL_API_KEY.lower():
        logger.warning("Mistral API key not configured, skipping AI scoring")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}
    
    try:
        # Prepare prompt
        prompt = f\"\"\"
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
\"\"\"
        
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Use agent ID if provided, otherwise use instructions
        if agent_id:
            response = client.agents.complete(
                agent_id=agent_id,
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            response = client.beta.conversations.start(
                inputs=[{"role": "user", "content": prompt}],
                model="mistral-small-latest",
                instructions=instructions,
                completion_args={
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "top_p": 1
                }
            )
        
        # Extract content
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)
        
        # Parse JSON response
        try:
            import json
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