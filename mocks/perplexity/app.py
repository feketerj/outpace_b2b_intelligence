"""
Perplexity Mock Server
Port: 8003
Endpoints:
  - POST /chat/completions
  - GET /health

Simulates Perplexity AI API for research/search augmented generation.
"""

import asyncio
import time
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Perplexity Mock Server", version="1.0.0")


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "pplx-7b-online"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "perplexity-mock", "port": 8003}


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    Mock Perplexity chat completions endpoint.
    Perplexity specializes in search-augmented responses with citations.
    """
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

    # ECHO trigger
    if last_message.startswith("ECHO:"):
        response_content = last_message[5:].strip()
        citations = []
    else:
        # Generate mock research response with citations
        response_content = generate_research_response(last_message)
        citations = generate_mock_citations(last_message)

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
        "citations": citations,
        "usage": {
            "prompt_tokens": sum(len(m.content.split()) for m in request.messages),
            "completion_tokens": len(response_content.split()),
            "total_tokens": sum(len(m.content.split()) for m in request.messages) + len(response_content.split())
        }
    }


def generate_research_response(query: str) -> str:
    """Generate a mock research-style response."""
    query_lower = query.lower()

    if "government" in query_lower or "contract" in query_lower:
        return (
            "Based on current federal contracting data, government IT spending is projected to reach "
            "$100 billion in FY2024 [1]. Key agencies driving this growth include the Department of Defense, "
            "which accounts for approximately 40% of federal IT spending [2], and the Department of Homeland "
            "Security, focusing on cybersecurity initiatives [3]. Small business set-asides represent roughly "
            "23% of all federal contracts, providing significant opportunities for qualifying firms [4]."
        )
    elif "cybersecurity" in query_lower or "security" in query_lower:
        return (
            "The federal cybersecurity market continues to expand rapidly, with the CISA budget increasing "
            "by 15% year-over-year [1]. Key focus areas include zero-trust architecture implementation, "
            "as mandated by Executive Order 14028 [2], and supply chain security following recent incidents [3]. "
            "Agencies are prioritizing endpoint detection and response (EDR) solutions and security operations "
            "center (SOC) modernization [4]."
        )
    else:
        return (
            "This is a mock research response from Perplexity. The query was processed successfully. "
            "In a production environment, this would contain search-augmented information with citations [1]. "
            "The response would include relevant data from multiple sources [2], synthesized into a coherent "
            "answer [3]."
        )


def generate_mock_citations(query: str) -> List[dict]:
    """Generate mock citations for the response."""
    return [
        {
            "url": "https://example.gov/it-spending-report-2024",
            "title": "Federal IT Spending Report FY2024",
            "snippet": "Comprehensive analysis of federal technology investments..."
        },
        {
            "url": "https://example.gov/dod-budget-overview",
            "title": "DoD Technology Budget Overview",
            "snippet": "Department of Defense technology spending priorities..."
        },
        {
            "url": "https://example.gov/cybersecurity-initiatives",
            "title": "Federal Cybersecurity Initiatives",
            "snippet": "Current federal cybersecurity programs and requirements..."
        },
        {
            "url": "https://example.gov/small-business-contracting",
            "title": "Small Business Federal Contracting Guide",
            "snippet": "Guide to federal contracting opportunities for small businesses..."
        }
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
