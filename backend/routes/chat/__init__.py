"""Chat routes package.

Inventory from legacy `backend/routes/chat.py`:
- Globals/constants: router, logger, CONVERSATION_ID_PATTERN, MAX_CONVERSATION_ID_LENGTH, MISTRAL_API_KEY
- Class: LLMServiceError
- Helpers: get_db, _to_dt, _tokenize, _build_knowledge_context,
  _retrieve_opportunities_context, _retrieve_intelligence_context
- Endpoints: send_chat_message (POST /message), get_chat_history (GET /history/{conversation_id}),
  get_chat_turns (GET /turns/{conversation_id})
- Major dependencies/cross-calls: backend.routes.rag.retrieve_rag_context, backend.utils.usage.record_external_usage,
  backend.utils.auth.get_current_user, backend.database.get_database, Mistral client SDK, tenant chat policy/quota logic.
"""

from datetime import datetime
import logging
import os
import re
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from mistralai import Mistral

from backend.database import get_database
from backend.models import ChatMessage, ChatTurn
from backend.utils.auth import TokenData, get_current_user
from backend.utils.secrets import get_secret
from backend.utils.usage import record_external_usage

from .domain_context import build_system_instructions, retrieve_intelligence_context, retrieve_opportunities_context
from .history import get_chat_history as load_chat_history
from .history import get_chat_turns as load_chat_turns
from .history import save_chat_turn
from .quota import check_quota, increment_quota, release_quota
from .rag_injection import build_knowledge_context, retrieve_rag_context_for_tenant

router = APIRouter()
logger = logging.getLogger(__name__)

CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_CONVERSATION_ID_LENGTH = 128
MISTRAL_API_KEY = get_secret("MISTRAL_API_KEY")


class LLMServiceError(Exception):
    """Raised when LLM service fails."""


def get_db():
    return get_database()


@router.post("/message")
async def send_chat_message(
    message_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user),
    x_debug_knowledge: Optional[str] = Header(None, alias="X-Debug-Knowledge"),
    x_debug_rag: Optional[str] = Header(None, alias="X-Debug-Rag"),
):
    db = get_db()
    debug_knowledge = x_debug_knowledge == "true" and current_user.role == "super_admin"
    debug_rag = x_debug_rag == "true" and current_user.role == "super_admin"

    conversation_id = message_data.get("conversation_id")
    user_message = message_data.get("message")
    agent_type = message_data.get("agent_type", "opportunities")

    requested_tenant_id = message_data.get("tenant_id")
    logger.info(
        "[chat.debug] role=%s user_tenant=%s requested_tenant=%s payload_keys=%s",
        current_user.role,
        current_user.tenant_id,
        requested_tenant_id,
        list(message_data.keys()),
    )
    effective_tenant_id = requested_tenant_id if requested_tenant_id and current_user.role == "super_admin" else current_user.tenant_id
    if requested_tenant_id and current_user.role == "super_admin":
        logger.info("[chat] super_admin using preview tenant: %s", effective_tenant_id)
    logger.info("[chat.debug] effective_tenant_id=%s", effective_tenant_id)

    if not conversation_id or not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="conversation_id and message are required")

    tenant = await db.tenants.find_one({"id": effective_tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    chat_policy = tenant.get("chat_policy", {})
    await check_quota(tenant)

    if len(conversation_id) > MAX_CONVERSATION_ID_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"conversation_id exceeds {MAX_CONVERSATION_ID_LENGTH} characters")
    if not CONVERSATION_ID_PATTERN.match(conversation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="conversation_id must contain only alphanumeric, dots, underscores, hyphens")

    max_user_chars = chat_policy.get("max_user_chars", 2000)
    if len(user_message) > max_user_chars:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"message exceeds {max_user_chars} characters")

    monthly_limit = chat_policy.get("monthly_message_limit")
    quota_reserved, _ = await increment_quota(db, effective_tenant_id, monthly_limit)

    max_assistant_tokens = chat_policy.get("max_assistant_tokens", 1000)
    max_turns_history = chat_policy.get("max_turns_history", 10)
    agent_config = tenant.get("agent_config", {})

    if agent_type == "opportunities":
        chat_agent_id = agent_config.get("opportunities_chat_agent_id")
        base_instructions = agent_config.get("opportunities_chat_instructions", "You are a helpful assistant.")
    else:
        chat_agent_id = agent_config.get("intelligence_chat_agent_id")
        base_instructions = agent_config.get("intelligence_chat_instructions", "You are a business intelligence analyst.")

    knowledge_context, snippet_ids_used = await build_knowledge_context(db, tenant, user_message)
    knowledge_injected_chars = len(knowledge_context)
    if knowledge_context:
        logger.info("[knowledge] Injected %s chars, snippets=%s", knowledge_injected_chars, snippet_ids_used)
    else:
        logger.debug("[knowledge] No knowledge context (disabled or empty)")

    rag_policy = tenant.get("rag_policy") or {}
    rag_context, rag_debug_info = await retrieve_rag_context_for_tenant(db, effective_tenant_id, user_message, rag_policy, debug=debug_rag)

    domain_context, domain_debug_info = "", {}
    if agent_type == "opportunities":
        domain_context, domain_debug_info = await retrieve_opportunities_context(db, effective_tenant_id, agent_config, debug=debug_rag)
    elif agent_type == "intelligence":
        domain_context, domain_debug_info = await retrieve_intelligence_context(db, effective_tenant_id, agent_config, debug=debug_rag)

    logger.info(
        "[domain.audit] tenant_id=%s conv=%s agent_type=%s reason=%s items_used=%s chars=%s",
        effective_tenant_id,
        conversation_id,
        agent_type,
        domain_debug_info.get("reason"),
        domain_debug_info.get("items_used"),
        domain_debug_info.get("context_chars"),
    )

    instructions = build_system_instructions(base_instructions, knowledge_context, rag_context, domain_context)

    history_turns = await db.chat_turns.find(
        {"tenant_id": effective_tenant_id, "conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).limit(max_turns_history).to_list(length=max_turns_history)

    inputs = []
    for turn in history_turns:
        inputs.append({"role": "user", "content": turn["user"]["content"]})
        inputs.append({"role": "assistant", "content": turn["assistant"]["content"]})
    inputs.append({"role": "user", "content": user_message})

    if not MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY not configured")
        await release_quota(db, effective_tenant_id, quota_reserved, monthly_limit)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM service not configured")

    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        api_start = time.monotonic()
        if chat_agent_id:
            logger.info("[chat] Using Mistral Agent: %s", chat_agent_id)
            context_prefix = f"[Context for this conversation:\n{instructions}\n]\n\n" if instructions != base_instructions else ""
            agent_messages = []
            for turn in history_turns:
                agent_messages.append({"role": "user", "content": turn["user"]["content"]})
                agent_messages.append({"role": "assistant", "content": turn["assistant"]["content"]})
            agent_messages.append({"role": "user", "content": context_prefix + user_message})
            response = client.agents.complete(agent_id=chat_agent_id, messages=agent_messages)
        else:
            logger.info("[chat] Using dynamic instructions (no agent ID)")
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "system", "content": instructions}] + inputs,
                temperature=0.7,
                max_tokens=max_assistant_tokens,
            )

        duration_ms = (time.monotonic() - api_start) * 1000
        await record_external_usage(
            db,
            effective_tenant_id,
            "mistral",
            "agents_complete" if chat_agent_id else "chat_complete",
            "success",
            duration_ms=duration_ms,
            metadata={"agent_id": chat_agent_id, "model": "mistral-small-latest", "has_agent": bool(chat_agent_id)},
        )
        assistant_content = response.choices[0].message.content

    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception("[chat_llm_error:%s] Mistral API error", err_id)
        duration_ms = (time.monotonic() - api_start) * 1000 if "api_start" in locals() else None
        await record_external_usage(
            db,
            effective_tenant_id,
            "mistral",
            "agents_complete" if chat_agent_id else "chat_complete",
            "error",
            duration_ms=duration_ms,
            metadata={"error": str(e), "agent_id": chat_agent_id},
        )
        await release_quota(db, effective_tenant_id, quota_reserved, monthly_limit)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"LLM service unavailable (error_id={err_id})")

    try:
        chat_turn_doc = await save_chat_turn(
            db,
            conversation_id=conversation_id,
            tenant_id=effective_tenant_id,
            user_id=current_user.user_id,
            user_message=user_message,
            assistant_content=assistant_content,
            agent_type=agent_type,
        )
    except Exception as e:
        logger.error("Database insert error: %s", e)
        await release_quota(db, effective_tenant_id, quota_reserved, monthly_limit)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save chat turn")

    logger.info(
        "[audit.chat] tenant_id=%s conv=%s turn_id=%s agent=%s user_chars=%s assistant_chars=%s",
        effective_tenant_id,
        conversation_id,
        chat_turn_doc["id"],
        agent_type,
        len(user_message),
        len(assistant_content),
    )

    response_data = {
        "id": f"{chat_turn_doc['id']}-assistant",
        "conversation_id": chat_turn_doc["conversation_id"],
        "tenant_id": chat_turn_doc["tenant_id"],
        "user_id": chat_turn_doc["user_id"],
        "role": "assistant",
        "content": chat_turn_doc["assistant"]["content"],
        "agent_id": chat_turn_doc["agent_type"],
        "created_at": chat_turn_doc["assistant"]["timestamp"],
    }

    if debug_knowledge or debug_rag:
        response_data["_debug"] = {}
        if debug_knowledge:
            response_data["_debug"]["knowledge_injected_chars"] = knowledge_injected_chars
            response_data["_debug"]["snippet_ids_used"] = snippet_ids_used
        if debug_rag:
            response_data["_debug"]["rag"] = rag_debug_info

    return response_data


@router.get("/history/{conversation_id}", response_model=List[ChatMessage])
async def get_chat_history(conversation_id: str, current_user: TokenData = Depends(get_current_user)):
    return await load_chat_history(get_db(), current_user.tenant_id, conversation_id)


@router.get("/turns/{conversation_id}", response_model=List[ChatTurn])
async def get_chat_turns(conversation_id: str, current_user: TokenData = Depends(get_current_user)):
    return await load_chat_turns(get_db(), current_user.tenant_id, conversation_id)


# Backward-compatible aliases for existing test imports
from .rag_injection import tokenize as _tokenize
_retrieve_opportunities_context = retrieve_opportunities_context
_retrieve_intelligence_context = retrieve_intelligence_context
_build_knowledge_context = build_knowledge_context

__all__ = ["router", "send_chat_message", "get_chat_history", "get_chat_turns"]
