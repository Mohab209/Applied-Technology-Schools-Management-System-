"""RAG service — chunking, embedding, storing, retrieving, generating."""
import os
from io import BytesIO
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm_service import PROVIDERS
from app.models import Document

load_dotenv()

# ============================================================
# Reuse the Groq client + model from llm_service (from Session 11)
# ============================================================
_groq_config = PROVIDERS["groq"]
groq_client = _groq_config["client"]
GROQ_MODEL = _groq_config["model"]

# ============================================================
# HuggingFace Inference API setup — for embeddings
# ============================================================
HF_TOKEN = os.getenv("HF_TOKEN")
HF_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HF_EMBEDDING_URL = f"https://router.huggingface.co/hf-inference/models/{HF_EMBEDDING_MODEL}/pipeline/feature-extraction"
EMBEDDING_DIM = 384

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in .env — required for embeddings")

# ============================================================
# Chunking config
# ============================================================
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ============================================================
# PDF extraction
# ============================================================
def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes.

    Accepts bytes because FastAPI's UploadFile gives us bytes, not a path.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(page_text)

    return "\n\n".join(text_parts)


# ============================================================
# Chunking
# ============================================================
def chunk_document(text: str, source: str) -> list[dict[str, Any]]:
    """Split text into chunks with metadata attached.

    Returns list of dicts: [{content, metadata}, ...]
    """
    chunks = _splitter.split_text(text)
    total = len(chunks)

    return [
        {
            "content": chunk,
            "metadata": {
                "source": source,
                "chunk_index": i,
                "total_chunks": total,
            },
        }
        for i, chunk in enumerate(chunks)
    ]


# ============================================================
# Embedding via HuggingFace Inference API
# ============================================================
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using HuggingFace Inference API.

    Returns a list of 384-dim vectors, one per input text.
    """
    if not texts:
        return []

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": texts,
        "options": {"wait_for_model": True},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(HF_EMBEDDING_URL, headers=headers, json=payload)
        response.raise_for_status()
        embeddings = response.json()

    if not isinstance(embeddings, list) or not embeddings:
        raise RuntimeError(f"Unexpected HF response: {embeddings!r}")

    return embeddings


# ============================================================
# Ingest: PDF → chunks → embeddings → Supabase
# ============================================================
async def ingest_document(
    pdf_bytes: bytes,
    filename: str,
    db: Session,
) -> int:
    """Full ingest pipeline: PDF → chunks → embeddings → DB.

    Returns the number of chunks stored.
    """
    # Step 1: Extract text
    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        raise ValueError(
            f"No text extracted from {filename!r}. "
            "The PDF may be scanned images — OCR is not supported."
        )

    # Step 2: Chunk
    chunks = chunk_document(text, source=filename)
    if not chunks:
        raise ValueError(f"Chunking produced 0 chunks for {filename!r}.")

    # Step 3: Extract just content strings for batch embedding
    contents = [c["content"] for c in chunks]

    # Step 4: Embed all chunks in ONE API call
    embeddings = await embed_texts(contents)

    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: got {len(embeddings)} for {len(chunks)} chunks"
        )

    # Step 5: Build Document objects
    docs = [
        Document(
            content=chunk["content"],
            embedding=embedding,
            doc_metadata=chunk["metadata"],
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    # Step 6: Bulk insert
    db.add_all(docs)
    db.commit()

    return len(docs)


# ============================================================
# Retrieval: query → top-K similar chunks
# ============================================================
async def retrieve_top_k(
    query: str,
    db: Session,
    k: int = 5,
) -> list[tuple[Document, float]]:
    """Retrieve top-K most similar chunks for a query."""
    # Step 1: Embed the query
    query_embeddings = await embed_texts([query])
    query_vec = query_embeddings[0]

    # Step 2: SQL query with cosine 
    distance = Document.embedding.cosine_distance(query_vec).label("distance")
    stmt = (
        select(Document, distance)
        .order_by(distance)
        .limit(k)
    )

    results = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in results]


# ============================================================
# Prompt building for RAG
# ============================================================
RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions strictly based on the provided context.

Rules:
- Use ONLY the information in the context to answer.
- If the context does not contain enough information to answer, reply with:
  "I don't have enough information in the provided context to answer that."
- Do not use any external knowledge.
- When possible, cite the source (e.g., "According to sample.pdf...").
- Be concise. Answer in 2-4 sentences unless the user asks for detail.
"""


def build_augmented_prompt(query: str, chunks: list[Document]) -> list[dict[str, str]]:
    """Build the OpenAI-format messages list with context injected."""
    # Build the context block
    context_parts = []
    for doc in chunks:
        meta = doc.doc_metadata or {}
        source = meta.get("source", "unknown")
        idx = meta.get("chunk_index", "?")
        context_parts.append(f"[Source: {source}, chunk {idx}]\n{doc.content}")

    context_block = "\n\n".join(context_parts)

    user_content = (
        f"Context:\n{context_block}\n\n"
        f"Question: {query}"
    )

    return [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ============================================================
# The full RAG query: retrieve + augment + generate
# ============================================================
async def answer_query(
    query: str,
    db: Session,
    k: int = 5,
) -> dict[str, Any]:
    """Full RAG loop: retrieve top-K, build prompt, call LLM, return answer + sources."""
    # Step 1: Retrieve
    results = await retrieve_top_k(query, db, k=k)

    if not results:
        return {
            "answer": "No documents in the knowledge base yet. please ingest a pdf first.",
            "sources": [],
        }
        
    # Unpack Tuples for downstream use
    chunks = [doc for doc, _ in results]
    distances = [dist for _, dist in results]

    # Step 2: Build the augmented prompt
    messages = build_augmented_prompt(query, chunks)

    # Step 3: Call the LLM
    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.2,  # low temp for factual answers
    )
    answer = response.choices[0].message.content

    # Step 4: Format sources for the response
    sources = [
        {
            "id": doc.id,
            "source": (doc.doc_metadata or {}).get("source", "unknown"),
            "chunk_index": (doc.doc_metadata or {}).get("chunk_index"),
            "distance": round(dist, 4),
            "preview": doc.content[:200],
        }
        for doc, dist in zip(chunks, distances)
    ]

    return {"answer": answer, "sources": sources}


# DISCOVERY: LIST INGESTED SOURCES
def list_ingested_sources(db: Session) -> list[dict[str, Any]]:
    """Return a list of unique document sources with chunk counts."""
    from sqlalchemy import func
    stmt = (
        select(
            Document.doc_metadata["source"].astext.label("source"),
            func.count(Document.id).label("chunk_count"),
            func.max(Document.created_at).label("last_ingested"),
        )
        .group_by(Document.doc_metadata["source"].astext)
        .order_by(func.max(Document.created_at).desc())
    )

    results = db.execute(stmt).all()

    return [
        {
            "source": row.source or "unknown",
            "chunk_count": row.chunk_count,
            "last_ingested": row.last_ingested.isoformat() if row.last_ingested else None,
        }
        for row in results
    ]