from datetime import datetime, timezone
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

def calculate_opportunity_score(
    opportunity: Dict[str, Any],
    weights: Dict[str, float]
) -> int:
    """
    Calculate opportunity score based on configurable weights.
    Score is 0-100.
    """
    score = 0
    
    # Value score (0-40 points based on weight)
    value_weight = weights.get("value_weight", 0.4)
    if opportunity.get("estimated_value"):
        try:
            value_str = opportunity["estimated_value"].replace("$", "").replace(",", "")
            value = float(value_str)
            # Normalize: $0-$10M maps to 0-40 points
            value_score = min((value / 10000000) * 40, 40) * value_weight / 0.4
            score += value_score
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse estimated_value '{opportunity.get('estimated_value')}': {e}")
    
    # Deadline urgency score (0-30 points based on weight)
    deadline_weight = weights.get("deadline_weight", 0.3)
    if opportunity.get("due_date"):
        try:
            due_date = opportunity["due_date"]
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            
            days_until_due = (due_date - datetime.now(timezone.utc)).days
            # More urgent = higher score
            if days_until_due <= 7:
                urgency_score = 30
            elif days_until_due <= 30:
                urgency_score = 20
            elif days_until_due <= 60:
                urgency_score = 10
            else:
                urgency_score = 5
            
            score += urgency_score * deadline_weight / 0.3
        except (ValueError, TypeError, AttributeError) as e:
            logger.debug(f"Could not parse due_date '{opportunity.get('due_date')}': {e}")
    
    # Keyword relevance score (0-30 points based on weight)
    relevance_weight = weights.get("relevance_weight", 0.3)
    keywords = opportunity.get("keywords", [])
    if keywords:
        # More matched keywords = higher score
        keyword_score = min(len(keywords) * 5, 30) * relevance_weight / 0.3
        score += keyword_score
    
    return int(min(score, 100))