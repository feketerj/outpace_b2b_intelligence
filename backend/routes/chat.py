from fastapi import APIRouter, HTTPException, status, Depends, Body, Header
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import os
import re
from mistralai import Mistral

from models import ChatMessage, ChatTurn
from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

# Input validation constants
CONVERSATION_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
MAX_CONVERSATION_ID_LENGTH = 128

def get_db():
    return get_database()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")


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


from fastapi import Header

@router.post("/message")
async def send_chat_message(
    message_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user),
    x_debug_knowledge: Optional[str] = Header(None, alias="X-Debug-Knowledge")
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
    Optional Header: X-Debug-Knowledge: true (super admin only) - returns knowledge debug info
    """
    db = get_db()
    
    # Debug mode only for super admins
    debug_knowledge = x_debug_knowledge == "true" and current_user.role == "super_admin"
    
    conversation_id = message_data.get("conversation_id")
    user_message = message_data.get("message")
    agent_type = message_data.get("agent_type", "opportunities")
    
    if not conversation_id or not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id and message are required"
        )
    
    # Get tenant configuration
    tenant = await db.tenants.find_one({"id": current_user.tenant_id})
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
        
        # Atomic reservation: try to reset month OR increment within limit
        # Strategy: Two-phase attempt for Mongo standalone (no transactions)
        
        # Phase 1: Try resetting if month changed (new month = fresh quota)
        reset_result = await db.tenants.update_one(
            {
                "id": current_user.tenant_id,
                "$or": [
                    {"chat_usage": None},
                    {"chat_usage.month": {"$ne": month_key}}
                ]
            },
            {
                "$set": {
                    "chat_usage": {"month": month_key, "messages_used": 1}
                }
            }
        )
        
        if reset_result.modified_count > 0:
            quota_reserved = True
            logger.info(f"[quota] New month reservation for tenant {current_user.tenant_id}: month={month_key}")
        else:
            # Phase 2: Same month - try incrementing if under limit
            inc_result = await db.tenants.update_one(
                {
                    "id": current_user.tenant_id,
                    "chat_usage.month": month_key,
                    "chat_usage.messages_used": {"$lt": monthly_limit}
                },
                {
                    "$inc": {"chat_usage.messages_used": 1}
                }
            )
            
            if inc_result.modified_count > 0:
                quota_reserved = True
                logger.info(f"[quota] Incremented usage for tenant {current_user.tenant_id}")
            else:
                # Quota exceeded
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Monthly chat limit exceeded"
                )
    
    # Get policy values for LLM call
    max_assistant_tokens = chat_policy.get("max_assistant_tokens", 1000)
    max_turns_history = chat_policy.get("max_turns_history", 10)
    
    agent_config = tenant.get("agent_config", {})
    
    # Determine base instructions based on agent type
    if agent_type == "opportunities":
        base_instructions = agent_config.get("opportunities_chat_instructions", "You are a helpful assistant.")
    else:
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
    
    # Get conversation history from chat_turns collection (last N turns per policy)
    history_cursor = db.chat_turns.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
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
                await db.tenants.update_one(
                    {"id": current_user.tenant_id, "chat_usage.messages_used": {"$gt": 0}},
                    {"$inc": {"chat_usage.messages_used": -1}}
                )
                logger.info(f"[quota] Released reservation for tenant {current_user.tenant_id}")
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
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": instructions}
            ] + inputs,
            temperature=0.7,
            max_tokens=max_assistant_tokens
        )
        assistant_content = response.choices[0].message.content
        
    except Exception as e:
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
        "tenant_id": current_user.tenant_id,
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
    
    # Return ChatMessage (assistant) for frontend compatibility
    return ChatMessage(
        id=f"{chat_turn_doc['id']}-assistant",
        conversation_id=chat_turn_doc["conversation_id"],
        tenant_id=chat_turn_doc["tenant_id"],
        user_id=chat_turn_doc["user_id"],
        role="assistant",
        content=chat_turn_doc["assistant"]["content"],
        agent_id=chat_turn_doc["agent_type"],
        created_at=_to_dt(chat_turn_doc["assistant"]["timestamp"])
    )


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
