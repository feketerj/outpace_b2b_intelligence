import logging

logger = logging.getLogger(__name__)


async def retrieve_opportunities_context(db, tenant_id: str, agent_config: dict, debug: bool = False) -> tuple:
    """Retrieve opportunities for context injection."""
    from backend.utils.invariants import assert_tenant_match

    debug_info = {"enabled": True, "reason": None, "items_searched": 0, "items_used": 0, "context_chars": 0}
    max_items = agent_config.get("opportunities_context_max_items", 10)
    min_score = agent_config.get("opportunities_context_min_score", 0)
    max_chars = agent_config.get("opportunities_context_max_chars", 3000)
    exclude_archived = agent_config.get("opportunities_context_exclude_archived", True)

    if not agent_config.get("opportunities_context_enabled", True):
        debug_info["enabled"] = False
        debug_info["reason"] = "disabled"
        return "", debug_info

    query = {"tenant_id": tenant_id}
    if min_score > 0:
        query["score"] = {"$gte": min_score}
    if exclude_archived:
        query["is_archived"] = {"$ne": True}

    opportunities = await db.opportunities.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "agency": 1, "due_date": 1, "estimated_value": 1, "score": 1, "client_status": 1, "tenant_id": 1},
    ).sort("score", -1).limit(max_items).to_list(length=max_items)
    debug_info["items_searched"] = len(opportunities)
    assert_tenant_match(opportunities, tenant_id, "opportunities_context")

    if not opportunities:
        debug_info["reason"] = "no_items"
        return "", debug_info

    context_parts = ["Current Opportunities:"]
    total_chars, items_used = len(context_parts[0]), 0
    for opp in opportunities:
        due_str = opp.get("due_date", "TBD")
        if hasattr(due_str, "strftime"):
            due_str = due_str.strftime("%Y-%m-%d")

        line = (
            f"- [{opp.get('client_status', 'new').upper()}] {opp['title']} "
            f"(Agency: {opp.get('agency', 'Unknown')}, Value: {opp.get('estimated_value', 'Unknown')}, "
            f"Due: {due_str}, Score: {opp.get('score', 0)})"
        )
        if total_chars + len(line) + 1 > max_chars:
            break
        context_parts.append(line)
        total_chars += len(line) + 1
        items_used += 1

    debug_info.update({"items_used": items_used, "context_chars": total_chars, "reason": "success"})
    if debug:
        debug_info["opp_ids"] = [o["id"] for o in opportunities[:items_used]]

    return "\n".join(context_parts), debug_info


async def retrieve_intelligence_context(db, tenant_id: str, agent_config: dict, debug: bool = False) -> tuple:
    """Retrieve intelligence items for context injection."""
    from backend.utils.invariants import assert_tenant_match

    debug_info = {"enabled": True, "reason": None, "items_searched": 0, "items_used": 0, "context_chars": 0}
    max_items = agent_config.get("intelligence_context_max_items", 5)
    max_chars = agent_config.get("intelligence_context_max_chars", 3000)
    exclude_archived = agent_config.get("intelligence_context_exclude_archived", True)

    if not agent_config.get("intelligence_context_enabled", True):
        debug_info["enabled"] = False
        debug_info["reason"] = "disabled"
        return "", debug_info

    query = {"tenant_id": tenant_id}
    if exclude_archived:
        query["is_archived"] = {"$ne": True}

    intel_items = await db.intelligence.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "type": 1, "created_at": 1, "tenant_id": 1},
    ).sort("created_at", -1).limit(max_items).to_list(length=max_items)
    debug_info["items_searched"] = len(intel_items)
    assert_tenant_match(intel_items, tenant_id, "intelligence_context")

    if not intel_items:
        debug_info["reason"] = "no_items"
        return "", debug_info

    context_parts = ["Recent Intelligence Reports:"]
    total_chars, items_used = len(context_parts[0]), 0
    for intel in intel_items:
        summary = intel.get("summary", "")[:200]
        line = f"- [{intel.get('type', 'news').upper()}] {intel['title']}: {summary}"
        if total_chars + len(line) + 1 > max_chars:
            break
        context_parts.append(line)
        total_chars += len(line) + 1
        items_used += 1

    debug_info.update({"items_used": items_used, "context_chars": total_chars, "reason": "success"})
    if debug:
        debug_info["intel_ids"] = [i["id"] for i in intel_items[:items_used]]

    return "\n".join(context_parts), debug_info


def build_system_instructions(base_instructions: str, knowledge_context: str = "", rag_context: str = "", domain_context: str = "") -> str:
    """Compose final system prompt with optional tenant contexts."""
    instructions = base_instructions
    if knowledge_context:
        instructions = f"""{instructions}

Tenant Knowledge (authoritative, do not contradict):
{knowledge_context}

Rules:
- If the user asks something that conflicts with the Tenant Knowledge above, prefer the knowledge and say so.
- Do not invent facts beyond what is in Tenant Knowledge.
- Do not claim any items listed under Prohibited Claims."""
    if rag_context:
        instructions = f"""{instructions}

Tenant Knowledge Snippets (retrieved via semantic search):
{rag_context}

Use these snippets to answer the user's question accurately."""
    if domain_context:
        instructions = f"""{instructions}

{domain_context}

Use this data to answer questions accurately. Reference specific items when relevant."""
    return instructions
