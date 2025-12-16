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
        
        # Use standard chat.complete API (not beta conversations)
        if agent_id:
            logger.info(f"Using Mistral agent ID: {agent_id}")
            # For now, use chat.complete with instructions in system message
            # Agent ID functionality would require different SDK method
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
        else:
            logger.info(f"Using dynamic instructions for scoring")
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
        
        # Extract content - standard format
        content = response.choices[0].message.content
        
        # Parse JSON response
        try:
            import json
            # Try to parse as JSON
            parsed = json.loads(content)
            
            # Extract relevance_summary
            relevance_summary = parsed.get("relevance_summary")
            if not relevance_summary and "analysis" in parsed:
                # Nested structure
                relevance_summary = parsed["analysis"].get("relevance_summary", {}).get("description")
            
            if not relevance_summary:
                # Just use first 200 chars of content as summary
                relevance_summary = content[:200]
            
            # Ensure backward compatibility
            if "suggested_score_adjustment" not in parsed and "score_adjustment" in parsed:
                parsed["suggested_score_adjustment"] = parsed["score_adjustment"]
            elif "suggested_score_adjustment" not in parsed:
                parsed["suggested_score_adjustment"] = 0
            
            # Store clean summary
            parsed["relevance_summary"] = relevance_summary
            
            return parsed
        except Exception as parse_error:
            # Not JSON - use content as-is (but clean it up)
            logger.warning(f"Failed to parse JSON, using raw content: {parse_error}")
            
            # Try to extract just the summary sentence
            if "The contract opportunity" in content:
                # Find the first complete sentence
                import re
                match = re.search(r'The contract opportunity[^.]*\.', content)
                if match:
                    content = match.group(0)
            
            return {
                "relevance_summary": content[:300] if len(content) > 300 else content,
                "suggested_score_adjustment": 0
            }
    
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        return {"relevance_summary": None, "suggested_score_adjustment": 0}