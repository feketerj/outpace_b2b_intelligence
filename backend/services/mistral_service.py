import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any
from mistralai import Mistral

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

async def score_opportunity_with_ai(opportunity: dict, tenant: dict) -> Dict[str, Any]:
    """
    Use Mistral agent to analyze and score an opportunity BEFORE display.
    Supports both Agent ID (pre-created) OR dynamic instructions.
    Uses configurable output schema per client.
    Returns: AI analysis matching the configured schema
    """
    agent_config = tenant.get("agent_config", {})
    agent_id = agent_config.get("scoring_agent_id")
    instructions = agent_config.get("scoring_instructions", "Analyze this contract opportunity.")
    output_schema = agent_config.get("scoring_output_schema", {
        "relevance_summary": "string",
        "score_adjustment": "number"
    })
    
    # Check if keys are configured
    if not MISTRAL_API_KEY or "placeholder" in MISTRAL_API_KEY.lower():
        logger.warning("Mistral API key not configured, skipping AI scoring")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}
    
    try:
        # Build schema description for prompt
        schema_fields = "\n".join([f"  \"{k}\": {v}" for k, v in output_schema.items()])
        
        # Prepare prompt with tenant context
        search_profile = tenant.get("search_profile", {})
        prompt = f"""
Analyze this government contract opportunity and provide insights.

OPPORTUNITY:
Title: {opportunity.get('title', '')}
Agency: {opportunity.get('agency', '')}
Description: {opportunity.get('description', '')[:800]}
Estimated Value: {opportunity.get('estimated_value', 'N/A')}
NAICS Code: {opportunity.get('naics_code', 'N/A')}
Due Date: {opportunity.get('due_date', 'N/A')}

TENANT PROFILE:
Company: {tenant.get('name', '')}
Interest Areas: {', '.join(search_profile.get('interest_areas', []))}
Competitors: {', '.join(search_profile.get('competitors', []))}
Keywords: {', '.join(search_profile.get('keywords', []))}

REQUIRED OUTPUT (JSON):
{{
{schema_fields}
}}

Provide a structured analysis following the schema above.
"""
        
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Use agent ID if provided, otherwise use instructions
        if agent_id:
            logger.info(f"Using Mistral agent ID: {agent_id}")
            response = client.agents.complete(
                agent_id=agent_id,
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            logger.info(f"Using dynamic instructions for scoring")
            response = client.beta.conversations.start(
                inputs=[{"role": "user", "content": prompt}],
                model="mistral-small-latest",
                instructions=instructions,
                completion_args={
                    "temperature": 0.3,
                    "max_tokens": 1000,
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
            
            # Ensure backward compatibility
            if "relevance_summary" not in parsed and "summary" in parsed:
                parsed["relevance_summary"] = parsed["summary"]
            if "suggested_score_adjustment" not in parsed and "score_adjustment" in parsed:
                parsed["suggested_score_adjustment"] = parsed["score_adjustment"]
            
            return parsed
        except Exception as parse_error:
            logger.warning(f"Failed to parse JSON, returning raw content: {parse_error}")
            return {
                "relevance_summary": content,
                "suggested_score_adjustment": 0
            }
    
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}