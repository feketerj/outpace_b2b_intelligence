from fastapi import APIRouter, HTTPException, status, Depends, Body, Header
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import time
import os
import re
from mistralai import Mistral

from backend.models import ChatMessage, ChatTurn
from backend.utils.auth import get_current_user, TokenData
from backend.database import get_database
from backend.utils.usage import record_external_usage
from backend.utils.secrets import get_secret

router = APIRouter()
logger = logging.getLogger(__name__)

# Input validation constants
CONVERSATION_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
MAX_CONVERSATION_ID_LENGTH = 128

def get_db():
    return get_database()

MISTRAL_API_KEY = get_secret("MISTRAL_API_KEY")


class LLMServiceError(Exception):
    """Raised when LLM service fails"""
    pass


def _to_dt(x):
    """Convert timestamp to datetime, handling str and datetime inputs."""
    if isinstance(x, datetime):
        return x
    if isinstance(x, str):
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


def _tokenize(text: str) -> set:
    """Simple tokenizer for keyword matching."""
    return set(re.findall(r'[a-z0-9]+', text.lower()))


async def _build_knowledge_context(db, tenant: dict, user_message: str) -> tuple:
    """
    Build knowledge context for Mini-RAG injection.
    Returns: (knowledge_context: str, snippet_ids_used: list)
    """
    knowledge = tenant.get("tenant_knowledge") or {}
    
    if not knowledge.get("enabled", False):
        return "", []
    
    max_chars = knowledge.get("max_context_chars", 2000)
    retrieval_mode = knowledge.get("retrieval_mode", "keyword")
    max_snippets = knowledge.get("max_snippets", 5)
    
    # Build base context from structured fields
    sections = []
    
    if knowledge.get("company_profile"):
        sections.append(f"Company Profile:\n{knowledge['company_profile']}")
    
    if knowledge.get("key_facts"):
        facts = "\n".join(f"• {f}" for f in knowledge["key_facts"] if f)
        if facts:
            sections.append(f"Key Facts:\n{facts}")
    
    if knowledge.get("offerings"):
        offerings = "\n".join(f"• {o}" for o in knowledge["offerings"] if o)
        if offerings:
            sections.append(f"Offerings:\n{offerings}")
    
    if knowledge.get("differentiators"):
        diffs = "\n".join(f"• {d}" for d in knowledge["differentiators"] if d)
        if diffs:
            sections.append(f"Differentiators:\n{diffs}")
    
    if knowledge.get("prohibited_claims"):
        prohibited = "\n".join(f"• {p}" for p in knowledge["prohibited_claims"] if p)
        if prohibited:
            sections.append(f"Prohibited Claims (do NOT make these claims):\n{prohibited}")
    
    if knowledge.get("tone_guidelines"):
        sections.append(f"Tone Guidelines:\n{knowledge['tone_guidelines']}")
    
    # Snippet retrieval (keyword mode)
    snippet_ids_used = []
    if retrieval_mode == "keyword" and max_snippets > 0:
        tenant_id = tenant.get("id")
        snippets_cursor = db.knowledge_snippets.find(
            {"tenant_id": tenant_id},
            {"_id": 0}
        )
        snippets = await snippets_cursor.to_list(length=100)
        
        if snippets:
            user_tokens = _tokenize(user_message)
            scored_snippets = []
            
            for snip in snippets:
                # Score by token overlap with content + tags
                snip_text = f"{snip.get('title', '')} {snip.get('content', '')} {' '.join(snip.get('tags', []))}"
                snip_tokens = _tokenize(snip_text)
                overlap = len(user_tokens & snip_tokens)
                if overlap > 0:
                    scored_snippets.append((overlap, snip))
            
            # Sort by score descending, take top N
            scored_snippets.sort(key=lambda x: x[0], reverse=True)
            top_snippets = scored_snippets[:max_snippets]
            
            if top_snippets:
                snip_texts = []
                for _, snip in top_snippets:
                    snip_texts.append(f"[{snip.get('title', 'Snippet')}]: {snip.get('content', '')}")
                    snippet_ids_used.append(snip.get("id"))
                sections.append(f"Relevant Snippets:\n" + "\n".join(snip_texts))
    
    # Combine and enforce max_context_chars
    knowledge_context = "\n\n".join(sections)
    if len(knowledge_context) > max_chars:
        knowledge_context = knowledge_context[:max_chars]
    
    return knowledge_context, snippet_ids_used


async def _retrieve_opportunities_context(
    db, tenant_id: str, agent_config: dict, debug: bool = False
) -> tuple:
    """
    Retrieve opportunities for context injection.
    Returns: (context_str, debug_info)

    INVARIANT: Query ALWAYS includes tenant_id filter.
    INVARIANT: Results validated with assert_tenant_match().
    """
    from backend.utils.invariants import assert_tenant_match

    debug_info = {"enabled": True, "reason": None, "items_searched": 0,
                  "items_used": 0, "context_chars": 0}

    # Config (with sensible defaults)
    max_items = agent_config.get("opportunities_context_max_items", 10)
    min_score = agent_config.get("opportunities_context_min_score", 0)
    max_chars = agent_config.get("opportunities_context_max_chars", 3000)
    exclude_archived = agent_config.get("opportunities_context_exclude_archived", True)

    # Check if disabled
    if not agent_config.get("opportunities_context_enabled", True):
        debug_info["enabled"] = False
        debug_info["reason"] = "disabled"
        return "", debug_info

    # Build query - tenant_id MANDATORY
    query = {"tenant_id": tenant_id}
    if min_score > 0:
        query["score"] = {"$gte": min_score}
    if exclude_archived:
        query["is_archived"] = {"$ne": True}

    # Fetch opportunities
    cursor = db.opportunities.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "agency": 1, "due_date": 1,
         "estimated_value": 1, "score": 1, "client_status": 1, "tenant_id": 1}
    ).sort("score", -1).limit(max_items)

    opportunities = await cursor.to_list(length=max_items)
    debug_info["items_searched"] = len(opportunities)

    # DEFENSE-IN-DEPTH: Verify tenant isolation
    assert_tenant_match(opportunities, tenant_id, "opportunities_context")

    if not opportunities:
        debug_info["reason"] = "no_items"
        return "", debug_info

    # Build context string with char limit
    context_parts = ["Current Opportunities:"]
    total_chars = len(context_parts[0])
    items_used = 0

    for opp in opportunities:
        due_str = opp.get("due_date", "TBD")
        if hasattr(due_str, 'strftime'):
            due_str = due_str.strftime("%Y-%m-%d")

        line = (f"- [{opp.get('client_status', 'new').upper()}] {opp['title']} "
                f"(Agency: {opp.get('agency', 'Unknown')}, "
                f"Value: {opp.get('estimated_value', 'Unknown')}, "
                f"Due: {due_str}, Score: {opp.get('score', 0)})")

        if total_chars + len(line) + 1 > max_chars:
            break

        context_parts.append(line)
        total_chars += len(line) + 1
        items_used += 1

    debug_info["items_used"] = items_used
    debug_info["context_chars"] = total_chars
    debug_info["reason"] = "success"
    if debug:
        debug_info["opp_ids"] = [o["id"] for o in opportunities[:items_used]]

    return "\n".join(context_parts), debug_info


async def _retrieve_intelligence_context(
    db, tenant_id: str, agent_config: dict, debug: bool = False
) -> tuple:
    """
    Retrieve intelligence items for context injection.
    Returns: (context_str, debug_info)

    INVARIANT: Query ALWAYS includes tenant_id filter.
    INVARIANT: Results validated with assert_tenant_match().
    """
    from backend.utils.invariants import assert_tenant_match

    debug_info = {"enabled": True, "reason": None, "items_searched": 0,
                  "items_used": 0, "context_chars": 0}

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

    cursor = db.intelligence.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "summary": 1, "type": 1,
         "created_at": 1, "tenant_id": 1}
    ).sort("created_at", -1).limit(max_items)

    intel_items = await cursor.to_list(length=max_items)
    debug_info["items_searched"] = len(intel_items)

    assert_tenant_match(intel_items, tenant_id, "intelligence_context")

    if not intel_items:
        debug_info["reason"] = "no_items"
        return "", debug_info

    context_parts = ["Recent Intelligence Reports:"]
    total_chars = len(context_parts[0])
    items_used = 0

    for intel in intel_items:
        summary = intel.get('summary', '')[:200]
        line = f"- [{intel.get('type', 'news').upper()}] {intel['title']}: {summary}"

        if total_chars + len(line) + 1 > max_chars:
            break

        context_parts.append(line)
        total_chars += len(line) + 1
        items_used += 1

    debug_info["items_used"] = items_used
    debug_info["context_chars"] = total_chars
    debug_info["reason"] = "success"
    if debug:
        debug_info["intel_ids"] = [i["id"] for i in intel_items[:items_used]]

    return "\n".join(context_parts), debug_info


@router.post("/message")
async def send_chat_message(
    message_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user),
    x_debug_knowledge: Optional[str] = Header(None, alias="X-Debug-Knowledge"),
    x_debug_rag: Optional[str] = Header(None, alias="X-Debug-Rag")
):
    """
    Send message to Mistral agent (ATOMIC).
    
    Atomicity guarantee:
    - LLM is called BEFORE any database write
    - Single document contains both user and assistant messages
    - If LLM fails, nothing is persisted
    - HTTP 503 returned on LLM failure (not 200 with fallback)
    
    Returns: ChatMessage (assistant) for frontend compatibility.
    Storage: ChatTurn (atomic single-document).
    
    Expects: {"conversation_id": str, "message": str, "agent_type": "opportunities" | "intelligence"}
    Optional: {"tenant_id": str} - super_admin only, for preview mode
    Optional Header: X-Debug-Knowledge: true (super admin only) - returns knowledge debug info
    """
    db = get_db()
    
    # Debug mode only for super admins
    debug_knowledge = x_debug_knowledge == "true" and current_user.role == "super_admin"
    debug_rag = x_debug_rag == "true" and current_user.role == "super_admin"
    
    conversation_id = message_data.get("conversation_id")
    user_message = message_data.get("message")
    agent_type = message_data.get("agent_type", "opportunities")
    
    # Tenant ID: allow super_admin to specify for preview mode
    requested_tenant_id = message_data.get("tenant_id")
    logger.info(f"[chat.debug] role={current_user.role} user_tenant={current_user.tenant_id} requested_tenant={requested_tenant_id} payload_keys={list(message_data.keys())}")
    if requested_tenant_id and current_user.role == "super_admin":
        effective_tenant_id = requested_tenant_id
        logger.info(f"[chat] super_admin using preview tenant: {effective_tenant_id}")
    else:
        effective_tenant_id = current_user.tenant_id
    logger.info(f"[chat.debug] effective_tenant_id={effective_tenant_id}")
    
    if not conversation_id or not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id and message are required"
        )
    
    # Get tenant configuration
    tenant = await db.tenants.find_one({"id": effective_tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # === CHAT POLICY ENFORCEMENT (before any LLM call) ===
    chat_policy = tenant.get("chat_policy", {})
    
    # Check if chat is enabled for tenant
    if not chat_policy.get("enabled", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat not enabled for tenant"
        )
    
    # Validate conversation_id format
    if len(conversation_id) > MAX_CONVERSATION_ID_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"conversation_id exceeds {MAX_CONVERSATION_ID_LENGTH} characters"
        )
    if not CONVERSATION_ID_PATTERN.match(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id must contain only alphanumeric, dots, underscores, hyphens"
        )
    
    # Validate message length
    max_user_chars = chat_policy.get("max_user_chars", 2000)
    if len(user_message) > max_user_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"message exceeds {max_user_chars} characters"
        )
    
    # === QUOTA RESERVATION (before LLM call to avoid wasting tokens) ===
    monthly_limit = chat_policy.get("monthly_message_limit")
    quota_reserved = False

    if monthly_limit is not None:
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")

        # SINGLE ATOMIC OPERATION using aggregation pipeline update (MongoDB 4.2+)
        # Handles both month reset AND quota check in one atomic find_one_and_update
        # No race window between check and increment
        from pymongo import ReturnDocument

        result = await db.tenants.find_one_and_update(
            {
                "id": effective_tenant_id,
                "$or": [
                    # Case 1: No usage record yet
                    {"chat_usage": None},
                    {"chat_usage": {"$exists": False}},
                    # Case 2: Different month (new month = reset)
                    {"chat_usage.month": {"$ne": month_key}},
                    # Case 3: Same month but under limit
                    {
                        "chat_usage.month": month_key,
                        "chat_usage.messages_used": {"$lt": monthly_limit}
                    }
                ]
            },
            [
                # Aggregation pipeline update - conditional logic in single atomic op
                {
                    "$set": {
                        "chat_usage": {
                            "$cond": {
                                "if": {
                                    "$or": [
                                        {"$eq": [{"$type": "$chat_usage"}, "missing"]},
                                        {"$eq": ["$chat_usage", None]},
                                        {"$ne": ["$chat_usage.month", month_key]}
                                    ]
                                },
                                # New month or first usage: reset to 1
                                "then": {"month": month_key, "messages_used": 1},
                                # Same month: increment
                                "else": {
                                    "month": "$chat_usage.month",
                                    "messages_used": {"$add": ["$chat_usage.messages_used", 1]}
                                }
                            }
                        }
                    }
                }
            ],
            return_document=ReturnDocument.AFTER
        )

        if result:
            quota_reserved = True
            new_usage = result.get("chat_usage", {}).get("messages_used", 0)
            logger.info(f"[quota] Atomic reservation for tenant {effective_tenant_id}: month={month_key}, usage={new_usage}/{monthly_limit}")
        else:
            # No document matched = quota exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Monthly chat limit exceeded"
            )
    
    # Get policy values for LLM call
    max_assistant_tokens = chat_policy.get("max_assistant_tokens", 1000)
    max_turns_history = chat_policy.get("max_turns_history", 10)
    
    agent_config = tenant.get("agent_config", {})

    # Determine agent ID and base instructions based on agent type
    if agent_type == "opportunities":
        chat_agent_id = agent_config.get("opportunities_chat_agent_id")
        base_instructions = agent_config.get("opportunities_chat_instructions", "You are a helpful assistant.")
    else:
        chat_agent_id = agent_config.get("intelligence_chat_agent_id")
        base_instructions = agent_config.get("intelligence_chat_instructions", "You are a business intelligence analyst.")
    
    # === MINI-RAG: Build and inject tenant knowledge ===
    knowledge_context, snippet_ids_used = await _build_knowledge_context(db, tenant, user_message)
    knowledge_injected_chars = len(knowledge_context)
    
    if knowledge_context:
        instructions = f"""{base_instructions}

Tenant Knowledge (authoritative, do not contradict):
{knowledge_context}

Rules:
- If the user asks something that conflicts with the Tenant Knowledge above, prefer the knowledge and say so.
- Do not invent facts beyond what is in Tenant Knowledge.
- Do not claim any items listed under Prohibited Claims."""
        logger.info(f"[knowledge] Injected {knowledge_injected_chars} chars, snippets={snippet_ids_used}")
    else:
        instructions = base_instructions
        logger.debug("[knowledge] No knowledge context (disabled or empty)")
    
    # === REAL RAG: Embeddings-based retrieval ===
    from backend.routes.rag import retrieve_rag_context
    rag_policy = tenant.get("rag_policy") or {}
    rag_context, rag_debug_info = await retrieve_rag_context(
        db, effective_tenant_id, user_message, rag_policy, debug=debug_rag
    )
    
    if rag_context:
        instructions = f"""{instructions}

Tenant Knowledge Snippets (retrieved via semantic search):
{rag_context}

Use these snippets to answer the user's question accurately."""
    
    # === RAG AUDIT LOG (always when RAG enabled, no secrets, Carfax-grade) ===
    if rag_policy.get("enabled", False):
        logger.info(
            "[rag.audit] tenant_id=%s conv=%s reason=%s searched=%s used=%s chars=%s",
            effective_tenant_id, conversation_id,
            rag_debug_info.get("reason"),
            rag_debug_info.get("chunks_searched"),
            rag_debug_info.get("chunks_used"),
            rag_debug_info.get("context_chars"),
        )

    # === DOMAIN CONTEXT: Opportunities/Intelligence injection ===
    domain_context = ""
    domain_debug_info = {}

    if agent_type == "opportunities":
        domain_context, domain_debug_info = await _retrieve_opportunities_context(
            db, effective_tenant_id, agent_config, debug=debug_rag
        )
    elif agent_type == "intelligence":
        domain_context, domain_debug_info = await _retrieve_intelligence_context(
            db, effective_tenant_id, agent_config, debug=debug_rag
        )

    if domain_context:
        instructions = f"""{instructions}

{domain_context}

Use this data to answer questions accurately. Reference specific items when relevant."""

    # Domain context audit log (always, following RAG pattern)
    logger.info(
        "[domain.audit] tenant_id=%s conv=%s agent_type=%s reason=%s items_used=%s chars=%s",
        effective_tenant_id, conversation_id, agent_type,
        domain_debug_info.get("reason"),
        domain_debug_info.get("items_used"),
        domain_debug_info.get("context_chars"),
    )

    # Get conversation history from chat_turns collection (last N turns per policy)
    history_cursor = db.chat_turns.find(
        {"tenant_id": effective_tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).limit(max_turns_history)
    history_turns = await history_cursor.to_list(length=max_turns_history)
    
    # Build messages from history
    inputs = []
    for turn in history_turns:
        inputs.append({"role": "user", "content": turn["user"]["content"]})
        inputs.append({"role": "assistant", "content": turn["assistant"]["content"]})
    inputs.append({"role": "user", "content": user_message})
    
    # Timestamps for the turn
    user_timestamp = datetime.now(timezone.utc).isoformat()
    
    # === ATOMIC SECTION START ===
    # INVARIANT: LLM must succeed before any DB write.
    # INVARIANT: ChatTurn insert is single-operation atomic persistence.
    # Any failure returns 5xx and persists nothing.
    
    # Helper to release quota reservation on failure (best-effort)
    async def release_quota():
        if quota_reserved and monthly_limit is not None:
            try:
                result = await db.tenants.update_one(
                    {"id": effective_tenant_id, "chat_usage.messages_used": {"$gt": 0}},
                    {"$inc": {"chat_usage.messages_used": -1}}
                )
                if result.modified_count == 0:
                    logger.warning(f"[quota] Release attempted but no update for tenant {effective_tenant_id}")
                else:
                    logger.info(f"[quota] Released reservation for tenant {effective_tenant_id}")
            except Exception as release_err:
                logger.warning(f"[quota] Failed to release reservation: {release_err}")
    
    if not MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY not configured")
        await release_quota()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service not configured"
        )
    
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        api_start = time.monotonic()

        if chat_agent_id:
            # Use Mistral Agents API for pre-created agents
            logger.info(f"[chat] Using Mistral Agent: {chat_agent_id}")
            # Agents need context injected into the user message since they have their own system prompt
            context_prefix = ""
            if instructions != base_instructions:
                # We have knowledge/RAG context to inject
                context_prefix = f"[Context for this conversation:\n{instructions}\n]\n\n"

            agent_messages = []
            for turn in history_turns:
                agent_messages.append({"role": "user", "content": turn["user"]["content"]})
                agent_messages.append({"role": "assistant", "content": turn["assistant"]["content"]})
            agent_messages.append({"role": "user", "content": context_prefix + user_message})

            response = client.agents.complete(
                agent_id=chat_agent_id,
                messages=agent_messages
            )
        else:
            # Fallback to chat.complete with dynamic instructions
            logger.info("[chat] Using dynamic instructions (no agent ID)")
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": instructions}
                ] + inputs,
                temperature=0.7,
                max_tokens=max_assistant_tokens
            )

        duration_ms = (time.monotonic() - api_start) * 1000
        await record_external_usage(
            db,
            effective_tenant_id,
            "mistral",
            "agents_complete" if chat_agent_id else "chat_complete",
            "success",
            duration_ms=duration_ms,
            metadata={
                "agent_id": chat_agent_id,
                "model": "mistral-small-latest",
                "has_agent": bool(chat_agent_id)
            }
        )
        assistant_content = response.choices[0].message.content

    except Exception as e:
        # Log error via usage tracking
        duration_ms = (time.monotonic() - api_start) * 1000 if "api_start" in locals() else None
        await record_external_usage(
            db,
            effective_tenant_id,
            "mistral",
            "agents_complete" if chat_agent_id else "chat_complete",
            "error",
            duration_ms=duration_ms,
            metadata={"error": str(e), "agent_id": chat_agent_id}
        )
        err_id = str(uuid.uuid4())
        logger.exception(f"[chat_llm_error:{err_id}] Mistral API error")
        await release_quota()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service unavailable (error_id={err_id})"
        )
    
    assistant_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Create atomic chat turn document
    chat_turn_doc = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "tenant_id": effective_tenant_id,
        "user_id": current_user.user_id,
        "user": {
            "content": user_message,
            "timestamp": user_timestamp
        },
        "assistant": {
            "content": assistant_content,
            "timestamp": assistant_timestamp
        },
        "agent_type": agent_type,
        "created_at": user_timestamp
    }
    
    # Single atomic INSERT - both messages in one document
    try:
        await db.chat_turns.insert_one(chat_turn_doc)
    except Exception as e:
        logger.error(f"Database insert error: {e}")
        await release_quota()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chat turn"
        )

    # === ATOMIC SECTION END ===

    logger.info(f"[audit.chat] tenant_id={effective_tenant_id} conv={conversation_id} turn_id={chat_turn_doc['id']} agent={agent_type} user_chars={len(user_message)} assistant_chars={len(assistant_content)}")
    
    # Build response
    response_data = {
        "id": f"{chat_turn_doc['id']}-assistant",
        "conversation_id": chat_turn_doc["conversation_id"],
        "tenant_id": chat_turn_doc["tenant_id"],
        "user_id": chat_turn_doc["user_id"],
        "role": "assistant",
        "content": chat_turn_doc["assistant"]["content"],
        "agent_id": chat_turn_doc["agent_type"],
        "created_at": chat_turn_doc["assistant"]["timestamp"]
    }
    
    # Add debug info for super admins with X-Debug-Knowledge or X-Debug-Rag headers
    if debug_knowledge or debug_rag:
        response_data["_debug"] = {}
        if debug_knowledge:
            response_data["_debug"]["knowledge_injected_chars"] = knowledge_injected_chars
            response_data["_debug"]["snippet_ids_used"] = snippet_ids_used
        if debug_rag:
            response_data["_debug"]["rag"] = rag_debug_info
    
    return response_data


@router.get("/history/{conversation_id}", response_model=List[ChatMessage])
async def get_chat_history(
    conversation_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get chat history for a conversation.
    DUAL-READ: Merges chat_turns (new) and chat_messages (legacy), sorted by created_at.
    """
    db = get_db()
    messages: List[ChatMessage] = []

    # --- SOURCE 1: chat_turns ---
    turns_cursor = db.chat_turns.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1)

    turns = await turns_cursor.to_list(length=100)

    for turn in turns:
        messages.append(ChatMessage(
            id=f"{turn['id']}-user",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="user",
            content=turn["user"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=_to_dt(turn["user"]["timestamp"]),
        ))
        messages.append(ChatMessage(
            id=f"{turn['id']}-assistant",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="assistant",
            content=turn["assistant"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=_to_dt(turn["assistant"]["timestamp"]),
        ))

    # --- SOURCE 2: legacy chat_messages (always) ---
    legacy_cursor = db.chat_messages.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1)

    legacy_msgs = await legacy_cursor.to_list(length=100)

    for msg in legacy_msgs:
        messages.append(ChatMessage(
            id=msg["id"],
            conversation_id=msg["conversation_id"],
            tenant_id=msg["tenant_id"],
            user_id=msg["user_id"],
            role=msg["role"],
            content=msg["content"],
            agent_id=msg.get("agent_id"),
            created_at=_to_dt(msg["created_at"]),
        ))

    # Sort by created_at for determinism
    messages.sort(key=lambda m: m.created_at)

    # De-dupe by id (in case same message exists in both sources)
    seen = set()
    deduped = []
    for m in messages:
        if m.id in seen:
            continue
        seen.add(m.id)
        deduped.append(m)

    return deduped


@router.get("/turns/{conversation_id}", response_model=List[ChatTurn])
async def get_chat_turns(
    conversation_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get chat turns for a conversation (native format).
    Each turn contains both user and assistant messages.
    """
    db = get_db()
    
    cursor = db.chat_turns.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1)
    
    turns = await cursor.to_list(length=100)
    return [ChatTurn(**turn) for turn in turns]
