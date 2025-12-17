"""
RAG (Retrieval-Augmented Generation) endpoints for tenant knowledge base.
Real embeddings + cosine similarity retrieval.
Super-admin only.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
import uuid
import logging
import os
import hashlib
import numpy as np
from typing import List, Optional
from mistralai import Mistral

from utils.auth import get_current_super_admin, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Chunking config
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def get_db():
    return get_database()


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Deterministic chunking with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += (chunk_size - overlap)
        if start >= len(text):
            break
    return chunks


def _get_embeddings(texts: List[str], model: str = "mistral-embed") -> List[List[float]]:
    """Get embeddings from Mistral API."""
    if not MISTRAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service not configured"
        )
    
    client = Mistral(api_key=MISTRAL_API_KEY)
    response = client.embeddings.create(
        model=model,
        inputs=texts
    )
    return [item.embedding for item in response.data]


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@router.get("/{tenant_id}/rag/status")
async def get_rag_status(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Get RAG status and capacity for a tenant."""
    db = get_db()
    
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    rag_policy = tenant.get("rag_policy") or {}
    
    # Count documents and chunks
    doc_count = await db.kb_documents.count_documents({"tenant_id": tenant_id})
    chunk_count = await db.kb_chunks.count_documents({"tenant_id": tenant_id})
    
    return {
        "tenant_id": tenant_id,
        "enabled": rag_policy.get("enabled", False),
        "documents": doc_count,
        "chunks": chunk_count,
        "max_documents": rag_policy.get("max_documents", 0),
        "max_chunks": rag_policy.get("max_chunks", 0),
        "top_k": rag_policy.get("top_k", 5),
        "min_score": rag_policy.get("min_score", 0.25),
        "embed_model": rag_policy.get("embed_model", "mistral-embed")
    }


@router.post("/{tenant_id}/rag/documents")
async def ingest_document(
    tenant_id: str,
    doc_data: dict,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """
    Ingest a document: chunk it, embed chunks, store in kb_documents + kb_chunks.
    Super-admin only.
    """
    db = get_db()
    
    # Validate tenant and RAG policy
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    if tenant.get("is_master_client"):
        raise HTTPException(status_code=403, detail="RAG not available for master tenants")
    
    rag_policy = tenant.get("rag_policy") or {}
    if not rag_policy.get("enabled", False):
        raise HTTPException(status_code=403, detail="RAG not enabled for this tenant")
    
    title = doc_data.get("title", "Untitled")
    content = doc_data.get("content", "")
    
    if not content.strip():
        raise HTTPException(status_code=400, detail="Document content is required")
    
    # Check capacity
    max_documents = rag_policy.get("max_documents", 0)
    max_chunks = rag_policy.get("max_chunks", 0)
    embed_model = rag_policy.get("embed_model", "mistral-embed")
    
    current_docs = await db.kb_documents.count_documents({"tenant_id": tenant_id})
    current_chunks = await db.kb_chunks.count_documents({"tenant_id": tenant_id})
    
    if current_docs >= max_documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document limit reached ({current_docs}/{max_documents})"
        )
    
    # Chunk the content
    chunks = _chunk_text(content)
    chunks_to_create = len(chunks)
    
    if current_chunks + chunks_to_create > max_chunks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chunk limit would be exceeded ({current_chunks}+{chunks_to_create} > {max_chunks})"
        )
    
    # Create document record
    now = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    doc_id = str(uuid.uuid4())
    
    doc_record = {
        "id": doc_id,
        "tenant_id": tenant_id,
        "title": title,
        "status": "processing",
        "created_at": now,
        "updated_at": now,
        "hash": content_hash,
        "byte_size": len(content.encode())
    }
    await db.kb_documents.insert_one(doc_record)
    
    try:
        # Embed all chunks
        logger.info(f"[rag] Embedding {len(chunks)} chunks for doc {doc_id}")
        embeddings = _get_embeddings(chunks, model=embed_model)
        
        # Store chunks with embeddings
        chunk_records = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_records.append({
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "document_id": doc_id,
                "chunk_index": idx,
                "text": chunk_text,
                "embedding": embedding,
                "embedding_model": embed_model,
                "created_at": now
            })
        
        if chunk_records:
            await db.kb_chunks.insert_many(chunk_records)
        
        # Update document status
        await db.kb_documents.update_one(
            {"id": doc_id},
            {"$set": {"status": "ready", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        logger.info(f"[rag] Document {doc_id} ingested: {len(chunks)} chunks")
        
        return {
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "status": "ready"
        }
        
    except Exception as e:
        # Cleanup on failure
        await db.kb_chunks.delete_many({"document_id": doc_id})
        await db.kb_documents.delete_one({"id": doc_id})
        logger.error(f"[rag] Ingestion failed for doc {doc_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.delete("/{tenant_id}/rag/documents/{doc_id}", status_code=204)
async def delete_document(
    tenant_id: str,
    doc_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Delete a document and its chunks."""
    db = get_db()
    
    # Verify document belongs to tenant
    doc = await db.kb_documents.find_one({"id": doc_id, "tenant_id": tenant_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete chunks first, then document
    await db.kb_chunks.delete_many({"document_id": doc_id, "tenant_id": tenant_id})
    await db.kb_documents.delete_one({"id": doc_id})
    
    logger.info(f"[rag] Deleted document {doc_id} and its chunks")
    return None


@router.get("/{tenant_id}/rag/documents")
async def list_documents(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """List all documents for a tenant."""
    db = get_db()
    
    cursor = db.kb_documents.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).sort("created_at", -1)
    
    docs = await cursor.to_list(length=100)
    
    # Add chunk counts
    for doc in docs:
        doc["chunk_count"] = await db.kb_chunks.count_documents({"document_id": doc["id"]})
    
    return docs


async def retrieve_rag_context(
    db,
    tenant_id: str,
    query: str,
    rag_policy: dict,
    debug: bool = False
) -> tuple:
    """
    Retrieve relevant chunks via cosine similarity.
    Returns: (context_text: str, debug_info: dict)
    """
    if not rag_policy.get("enabled", False):
        return "", {"rag_enabled": False}
    
    max_chunks = rag_policy.get("max_chunks", 0)
    if max_chunks == 0:
        return "", {"rag_enabled": True, "max_chunks": 0}
    
    top_k = rag_policy.get("top_k", 5)
    min_score = rag_policy.get("min_score", 0.25)
    max_context_chars = rag_policy.get("max_context_chars", 2000)
    embed_model = rag_policy.get("embed_model", "mistral-embed")
    
    # Get query embedding
    try:
        query_embedding = _get_embeddings([query], model=embed_model)[0]
    except Exception as e:
        logger.error(f"[rag] Failed to embed query: {e}")
        return "", {"error": str(e)}
    
    # Fetch tenant's chunks (newest first, up to max_chunks)
    cursor = db.kb_chunks.find(
        {"tenant_id": tenant_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(max_chunks)
    
    chunks = await cursor.to_list(length=max_chunks)
    
    if not chunks:
        return "", {"rag_enabled": True, "chunks_found": 0}
    
    # Score chunks by cosine similarity
    scored = []
    for chunk in chunks:
        embedding = chunk.get("embedding", [])
        if embedding:
            score = _cosine_similarity(query_embedding, embedding)
            if score >= min_score:
                scored.append({
                    "chunk_id": chunk["id"],
                    "document_id": chunk["document_id"],
                    "text": chunk["text"],
                    "score": round(score, 4)
                })
    
    # Sort by score descending, take top_k
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_chunks = scored[:top_k]
    
    if not top_chunks:
        return "", {"rag_enabled": True, "chunks_found": len(chunks), "matches": 0}
    
    # Build context (trim to max_context_chars)
    context_parts = []
    total_chars = 0
    used_ids = []
    scores = []
    
    for chunk in top_chunks:
        text = chunk["text"]
        if total_chars + len(text) > max_context_chars:
            remaining = max_context_chars - total_chars
            if remaining > 50:  # Only add if meaningful
                text = text[:remaining]
            else:
                break
        context_parts.append(text)
        used_ids.append(chunk["chunk_id"])
        scores.append(chunk["score"])
        total_chars += len(text)
    
    context_text = "\n\n".join(context_parts)
    
    debug_info = {
        "rag_enabled": True,
        "chunks_searched": len(chunks),
        "matches_above_min_score": len(scored),
        "chunks_used": len(used_ids),
        "chunk_ids": used_ids if debug else None,
        "scores": scores if debug else None,
        "context_chars": len(context_text)
    }
    
    return context_text, debug_info
