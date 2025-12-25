"""
Mistral AI Mock Server
Port: 8001
Endpoints:
  - POST /v1/chat/completions
  - POST /v1/embeddings
  - GET /health

Triggers:
  - ECHO: prefix in message returns the message content as-is
  - FORCE_ERROR: returns 500 error
  - FORCE_TIMEOUT: sleeps for 30 seconds before responding
"""

import asyncio
import time
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any

app = FastAPI(title="Mistral Mock Server", version="1.0.0")


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mistral-medium"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False


class EmbeddingRequest(BaseModel):
    model: str = "mistral-embed"
    input: Any  # Can be string or list of strings


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mistral-mock", "port": 8001}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # Get last user message for trigger detection
    last_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            last_message = msg.content
            break

    # Check triggers
    if "FORCE_ERROR" in last_message:
        raise HTTPException(status_code=500, detail="Forced error triggered")

    if "FORCE_TIMEOUT" in last_message:
        await asyncio.sleep(30)

    # ECHO trigger - return message content as-is
    response_content = "This is a mock response from Mistral."
    if last_message.startswith("ECHO:"):
        response_content = last_message[5:].strip()

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": sum(len(m.content.split()) for m in request.messages),
            "completion_tokens": len(response_content.split()),
            "total_tokens": sum(len(m.content.split()) for m in request.messages) + len(response_content.split())
        }
    }


@app.post("/v1/embeddings")
async def embeddings(request: EmbeddingRequest):
    # Normalize input to list
    inputs = request.input if isinstance(request.input, list) else [request.input]

    # Check triggers in any input
    for text in inputs:
        if isinstance(text, str):
            if "FORCE_ERROR" in text:
                raise HTTPException(status_code=500, detail="Forced error triggered")
            if "FORCE_TIMEOUT" in text:
                await asyncio.sleep(30)

    # Generate mock embeddings (1024 dimensions of deterministic values)
    embeddings_data = []
    for idx, text in enumerate(inputs):
        # Create deterministic embedding based on text hash
        text_str = str(text)
        seed = hash(text_str) % 10000
        embedding = [(seed + i) % 1000 / 1000.0 for i in range(1024)]
        embeddings_data.append({
            "object": "embedding",
            "index": idx,
            "embedding": embedding
        })

    return {
        "object": "list",
        "data": embeddings_data,
        "model": request.model,
        "usage": {
            "prompt_tokens": sum(len(str(t).split()) for t in inputs),
            "total_tokens": sum(len(str(t).split()) for t in inputs)
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
