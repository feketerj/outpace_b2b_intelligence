from datetime import datetime, timezone
from typing import List
import uuid

from backend.models import ChatMessage, ChatTurn


def to_dt(x):
    """Convert timestamp to datetime, handling str and datetime inputs."""
    if isinstance(x, datetime):
        return x
    if isinstance(x, str):
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)


async def get_chat_history(db, tenant_id: str, conversation_id: str) -> List[ChatMessage]:
    """DUAL-READ history from chat_turns and legacy chat_messages, sorted and deduped."""
    messages: List[ChatMessage] = []

    turns = await db.chat_turns.find(
        {"tenant_id": tenant_id, "conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(length=100)

    for turn in turns:
        messages.append(ChatMessage(
            id=f"{turn['id']}-user",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="user",
            content=turn["user"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=to_dt(turn["user"]["timestamp"]),
        ))
        messages.append(ChatMessage(
            id=f"{turn['id']}-assistant",
            conversation_id=turn["conversation_id"],
            tenant_id=turn["tenant_id"],
            user_id=turn["user_id"],
            role="assistant",
            content=turn["assistant"]["content"],
            agent_id=turn.get("agent_type"),
            created_at=to_dt(turn["assistant"]["timestamp"]),
        ))

    legacy_msgs = await db.chat_messages.find(
        {"tenant_id": tenant_id, "conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(length=100)
    for msg in legacy_msgs:
        messages.append(ChatMessage(
            id=msg["id"],
            conversation_id=msg["conversation_id"],
            tenant_id=msg["tenant_id"],
            user_id=msg["user_id"],
            role=msg["role"],
            content=msg["content"],
            agent_id=msg.get("agent_id"),
            created_at=to_dt(msg["created_at"]),
        ))

    messages.sort(key=lambda m: m.created_at)
    deduped, seen = [], set()
    for m in messages:
        if m.id in seen:
            continue
        seen.add(m.id)
        deduped.append(m)
    return deduped


async def get_chat_turns(db, tenant_id: str, conversation_id: str) -> List[ChatTurn]:
    turns = await db.chat_turns.find(
        {"tenant_id": tenant_id, "conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(length=100)
    return [ChatTurn(**turn) for turn in turns]


async def save_chat_turn(db, *, conversation_id: str, tenant_id: str, user_id: str, user_message: str, assistant_content: str, agent_type: str):
    """Persist single atomic chat turn document."""
    user_timestamp = datetime.now(timezone.utc).isoformat()
    assistant_timestamp = datetime.now(timezone.utc).isoformat()
    chat_turn_doc = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "user": {"content": user_message, "timestamp": user_timestamp},
        "assistant": {"content": assistant_content, "timestamp": assistant_timestamp},
        "agent_type": agent_type,
        "created_at": user_timestamp,
    }
    await db.chat_turns.insert_one(chat_turn_doc)
    return chat_turn_doc


async def list_conversations(db, tenant_id: str):
    """Conversation listing helper retained for package completeness."""
    return await db.chat_turns.distinct("conversation_id", {"tenant_id": tenant_id})
