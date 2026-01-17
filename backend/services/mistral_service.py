import logging
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any
from mistralai import Mistral
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.utils.resilience import (
    circuit_protected,
    mistral_circuit,
    CircuitOpenError
)
from backend.utils.usage import record_external_usage
from backend.utils.secrets import get_secret

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = get_secret("MISTRAL_API_KEY")


@circuit_protected(mistral_circuit)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def score_opportunity_with_ai(opportunity: dict, tenant: dict, db=None) -> Dict[str, Any]:
    """
    Use Mistral agent to analyze and score an opportunity BEFORE display.
    Supports both Agent ID (pre-created) OR dynamic instructions.
    Uses configurable output schema per client.
    Returns: AI analysis matching the configured schema

    Protected by circuit breaker and retry logic.
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

        start_time = time.monotonic()
        if agent_id:
            # Use Mistral Agents API for pre-created agents
            logger.info(f"Using Mistral Agent: {agent_id}")
            response = client.agents.complete(
                agent_id=agent_id,
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            # Fallback to chat.complete with dynamic instructions
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
        duration_ms = (time.monotonic() - start_time) * 1000
        await record_external_usage(
            db,
            tenant.get("id"),
            "mistral",
            "score_opportunity",
            "success",
            duration_ms=duration_ms,
            metadata={
                "agent_id": agent_id,
                "model": "mistral-small-latest",
                "has_agent": bool(agent_id)
            }
        )
        
        # Extract content - standard format
        content = response.choices[0].message.content
        
        # Parse JSON response
        try:
            import json
            import re
            
            # Clean content first - remove markdown code blocks
            clean_content = content
            if '```json' in content:
                # Extract JSON from markdown code block
                match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if match:
                    clean_content = match.group(1)
            elif '```' in content:
                # Remove any code block markers
                clean_content = content.replace('```json', '').replace('```', '').strip()
            
            # Try to parse as JSON
            parsed = json.loads(clean_content)
            
            # Extract relevance_summary from various possible structures
            relevance_summary = None
            
            # Direct field
            if "relevance_summary" in parsed:
                relevance_summary = parsed["relevance_summary"]
            # Nested in analysis
            elif "analysis" in parsed and isinstance(parsed["analysis"], dict):
                if "relevance_summary" in parsed["analysis"]:
                    rel_sum = parsed["analysis"]["relevance_summary"]
                    if isinstance(rel_sum, dict) and "description" in rel_sum:
                        relevance_summary = rel_sum["description"]
                    elif isinstance(rel_sum, str):
                        relevance_summary = rel_sum
            
            # If still no summary, use the whole content but clean it
            if not relevance_summary:
                relevance_summary = clean_content[:300]
            
            # Get score adjustment
            score_adj = parsed.get("score_adjustment", 0)
            if not score_adj and "analysis" in parsed:
                # Might be nested
                score_adj = parsed["analysis"].get("score_adjustment", 0)
            
            return {
                "relevance_summary": relevance_summary,
                "suggested_score_adjustment": score_adj
            }
            
        except Exception as parse_error:
            # Not JSON - use content as-is (but clean it up)
            logger.warning(f"Failed to parse JSON: {parse_error}")
            
            # Remove markdown if present
            clean = content.replace('```json', '').replace('```', '').strip()
            
            # Try to extract just a readable sentence
            if "The contract opportunity" in clean:
                # Find the first complete sentence
                import re
                match = re.search(r'The contract opportunity[^.]*\.', clean)
                if match:
                    clean = match.group(0)
            
            return {
                "relevance_summary": clean[:300] if len(clean) > 300 else clean,
                "suggested_score_adjustment": 0
            }
    
    except Exception as e:
        # Log error via usage tracking
        duration_ms = (time.monotonic() - start_time) * 1000 if "start_time" in locals() else None
        await record_external_usage(
            db,
            tenant.get("id"),
            "mistral",
            "score_opportunity",
            "error",
            duration_ms=duration_ms,
            metadata={"error": str(e), "agent_id": tenant.get("agent_config", {}).get("scoring_agent_id")}
        )
        logger.error(f"[mistral.scoring] API_ERROR: {e}")
        return {
            "relevance_summary": None,
            "suggested_score_adjustment": 0,
            "ai_scoring_failed": True,
            "ai_error": str(e)
        }