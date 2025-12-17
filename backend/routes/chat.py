from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import List
from datetime import datetime, timezone
import uuid
import logging
import os
from mistralai import Mistral

from models import ChatMessage, ChatTurn
from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")


class LLMServiceError(Exception):
    """Raised when LLM service fails"""
    pass


@router.post("/message", response_model=ChatTurn)
async def send_chat_message(
    message_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Send message to Mistral agent (ATOMIC).
    
    Atomicity guarantee:
    - LLM is called BEFORE any database write
    - Single document contains both user and assistant messages
    - If LLM fails, nothing is persisted
    - HTTP 503 returned on LLM failure (not 200 with fallback)
    
    Expects: {"conversation_id": str, "message": str, "agent_type": "opportunities" | "intelligence"}
    """
    db = get_db()
    
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
    
    agent_config = tenant.get("agent_config", {})
    
    # Determine instructions based on agent type
    if agent_type == "opportunities":
        instructions = agent_config.get("opportunities_chat_instructions", "You are a helpful assistant.")
    else:
        instructions = agent_config.get("intelligence_chat_instructions", "You are a business intelligence analyst.")
    
    # Get conversation history from chat_turns collection
    history_cursor = db.chat_turns.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).limit(10)
    history_turns = await history_cursor.to_list(length=10)
    
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
    
    if not MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY not configured")
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
            max_tokens=2000
        )
        assistant_content = response.choices[0].message.content
        
    except Exception as e:
        err_id = str(uuid.uuid4())
        logger.exception(f"[chat_llm_error:{err_id}] Mistral API error")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save chat turn"
        )
    
    # === ATOMIC SECTION END ===
    
    return ChatTurn(**chat_turn_doc)


def _to_dt(x):
    """Convert timestamp to datetime, handling str and datetime inputs."""
    if isinstance(x, datetime):
        return x
    if isinstance(x, str):
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


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
