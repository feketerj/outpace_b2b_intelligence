from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import List
from datetime import datetime, timezone
import uuid
import logging
import os
from mistralai import Mistral

from models import ChatMessage, ChatMessageCreate
from utils.auth import get_current_user, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

@router.post("/message", response_model=ChatMessage)
async def send_chat_message(
    message_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Send message to Mistral agent.
    Supports BOTH agent IDs (pre-created agents) OR dynamic instructions.
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
    
    # Determine agent ID OR instructions based on what's configured
    if agent_type == "opportunities":
        agent_id = agent_config.get("opportunities_chat_agent_id")
        instructions = agent_config.get("opportunities_chat_instructions", "You are a helpful assistant.")
    else:
        agent_id = agent_config.get("intelligence_chat_agent_id")
        instructions = agent_config.get("intelligence_chat_instructions", "You are a business intelligence analyst.")
    
    # Get conversation history (last 10 messages)
    history_cursor = db.chat_messages.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).limit(10)
    history = await history_cursor.to_list(length=10)
    
    # Build messages
    inputs = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
    ]
    inputs.append({"role": "user", "content": user_message})
    
    # Save user message
    now = datetime.now(timezone.utc).isoformat()
    user_msg_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.user_id,
        "conversation_id": conversation_id,
        "role": "user",
        "content": user_message,
        "agent_id": agent_id or agent_type,
        "created_at": now
    }
    await db.chat_messages.insert_one(user_msg_doc)
    
    # Call Mistral API
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Use standard chat.complete API
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": instructions}
            ] + inputs,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Extract content
        assistant_content = response.choices[0].message.content
            
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        assistant_content = "I'm having trouble processing your request right now. Please try again."
    
    # Save assistant response
    assistant_msg_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.user_id,
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": assistant_content,
        "agent_id": agent_id or agent_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.chat_messages.insert_one(assistant_msg_doc)
    
    return ChatMessage(**assistant_msg_doc)

@router.get("/history/{conversation_id}", response_model=List[ChatMessage])
async def get_chat_history(
    conversation_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get chat history for a conversation"""
    db = get_db()
    
    cursor = db.chat_messages.find(
        {"tenant_id": current_user.tenant_id, "conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1)
    
    messages = await cursor.to_list(length=100)
    return [ChatMessage(**msg) for msg in messages]