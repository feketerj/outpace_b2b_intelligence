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
    # Call LLM FIRST - if this fails, no DB write occurs
    
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
        logger.error(f"Mistral API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service unavailable: {str(e)[:100]}"
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


@router.get("/history/{conversation_id}", response_model=List[ChatMessage])
async def get_chat_history(
    conversation_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get chat history for a conversation.
    Returns flattened list of messages (user, assistant, user, assistant...) for compatibility.
    """
    db = get_db()
    
    # Query chat_turns collection
    cursor = db.chat_turns.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1)
    
    turns = await cursor.to_list(length=100)
    
    # Flatten turns into message list for backward compatibility
    messages = []
    for turn in turns:
        # User message
        messages.append(ChatMessage(
            id=f"{turn['id']}-user",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="user",
            content=turn["user"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=datetime.fromisoformat(turn["user"]["timestamp"].replace('Z', '+00:00'))
        ))
        # Assistant message
        messages.append(ChatMessage(
            id=f"{turn['id']}-assistant",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="assistant",
            content=turn["assistant"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=datetime.fromisoformat(turn["assistant"]["timestamp"].replace('Z', '+00:00'))
        ))
    
    return messages


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
