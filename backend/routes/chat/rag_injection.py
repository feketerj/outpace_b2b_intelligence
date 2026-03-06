from datetime import datetime, timezone
import logging
import re

logger = logging.getLogger(__name__)


def tokenize(text: str) -> set:
    """Simple tokenizer for keyword matching."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


async def build_knowledge_context(db, tenant: dict, user_message: str) -> tuple:
    """Build knowledge context for Mini-RAG injection."""
    knowledge = tenant.get("tenant_knowledge") or {}

    if not knowledge.get("enabled", False):
        return "", []

    max_chars = knowledge.get("max_context_chars", 2000)
    retrieval_mode = knowledge.get("retrieval_mode", "keyword")
    max_snippets = knowledge.get("max_snippets", 5)

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

    snippet_ids_used = []
    if retrieval_mode == "keyword" and max_snippets > 0:
        tenant_id = tenant.get("id")
        snippets = await db.knowledge_snippets.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(length=100)
        if snippets:
            user_tokens = tokenize(user_message)
            scored_snippets = []
            for snip in snippets:
                snip_text = f"{snip.get('title', '')} {snip.get('content', '')} {' '.join(snip.get('tags', []))}"
                overlap = len(user_tokens & tokenize(snip_text))
                if overlap > 0:
                    scored_snippets.append((overlap, snip))

            scored_snippets.sort(key=lambda x: x[0], reverse=True)
            if top_snippets := scored_snippets[:max_snippets]:
                snip_texts = []
                for _, snip in top_snippets:
                    snip_texts.append(f"[{snip.get('title', 'Snippet')}]: {snip.get('content', '')}")
                    snippet_ids_used.append(snip.get("id"))
                sections.append("Relevant Snippets:\n" + "\n".join(snip_texts))

    knowledge_context = "\n\n".join(sections)
    if len(knowledge_context) > max_chars:
        knowledge_context = knowledge_context[:max_chars]

    return knowledge_context, snippet_ids_used


async def retrieve_rag_context_for_tenant(db, tenant_id: str, user_message: str, rag_policy: dict, debug: bool = False):
    """Proxy helper for existing semantic RAG retrieval."""
    from backend.routes.rag import retrieve_rag_context

    rag_context, rag_debug_info = await retrieve_rag_context(db, tenant_id, user_message, rag_policy, debug=debug)
    if rag_policy.get("enabled", False):
        logger.info(
            "[rag.audit] tenant_id=%s reason=%s searched=%s used=%s chars=%s",
            tenant_id,
            rag_debug_info.get("reason"),
            rag_debug_info.get("chunks_searched"),
            rag_debug_info.get("chunks_used"),
            rag_debug_info.get("context_chars"),
        )
    return rag_context, rag_debug_info
