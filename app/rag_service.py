"""RAG service — Production-ready, dynamically filtered by school_id."""
import os
from io import BytesIO
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm_service import PROVIDERS
from app.models import Document

load_dotenv()

_groq_config = PROVIDERS["groq"]
groq_client = _groq_config["client"]
GROQ_MODEL = _groq_config["model"]

HF_TOKEN = os.getenv("HF_TOKEN")
HF_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HF_EMBEDDING_URL = f"https://router.huggingface.co/hf-inference/models/{HF_EMBEDDING_MODEL}/pipeline/feature-extraction"

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in .env — required for embeddings")

CHUNK_SIZE = 2500
CHUNK_OVERLAP = 250

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", "؟ ", "، ", ". ", " ", ""],
)

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes."""
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def chunk_document(text: str, source: str) -> list[dict[str, Any]]:
    """Split text into chunks and label metadata."""
    raw_chunks = _splitter.split_text(text)
    total = len(raw_chunks)
    return [
        {
            "content": f"المستند المرجعي: {source}\nالنص التفصيلي: {chunk}",
            "metadata": {
                "source": source,
                "chunk_index": i,
                "total_chunks": total,
            },
        }
        for i, chunk in enumerate(raw_chunks)
    ]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using HuggingFace Inference API."""
    if not texts:
        return []
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": texts, "options": {"wait_for_model": True}}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(HF_EMBEDDING_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def ingest_document(pdf_bytes: bytes, filename: str, school_id: int, db: Session) -> int:
    """Full ingest pipeline linking chunks to specific school_id."""
    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        raise ValueError(f"No text extracted from {filename!r}.")

    chunks = chunk_document(text, source=filename)
    contents = [c["content"] for c in chunks]
    embeddings = await embed_texts(contents)

    docs = [
        Document(
            content=chunk["content"],
            embedding=embedding,
            doc_metadata=chunk["metadata"],
            school_id=school_id  # ربط ديناميكي
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    db.add_all(docs)
    db.commit()
    return len(docs)


async def retrieve_top_k(query: str, db: Session, school_id: int, k: int = 6) -> list[tuple[Document, float]]:
    """Strictly retrieve chunks filtered by school_id using cosine_distance."""
    query_embeddings = await embed_texts([query])
    query_vec = query_embeddings[0]

    distance = Document.embedding.cosine_distance(query_vec).label("distance")
    
    # فلترة صارمة وحتمية برقم المدرسة لمنع اختلاط المستندات
    stmt = (
        select(Document, distance)
        .where(Document.school_id == school_id)
        .order_by(distance.asc())
        .limit(k)
    )

    results = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in results]


RAG_SYSTEM_PROMPT = """أنت مساعد ذكي ومحترف في نظام إدارة مدارس التكنولوجيا التطبيقية. مهمتك الإجابة عن أسئلة المستخدمين بدقة وبناءً على النصوص المرجعية المرفقة المفلترة خصيصاً للمدرسة الحالية.
أجب بوضوح وباللغة العربية الفصحى دون اختراع تفاصيل غير مذكورة صراحة في النص. إذا لم تجد الإجابة، قل: "عذراً، لا تتوفر معلومات تفصيلية حول هذا السؤال في الدليل الحالي لهذه المدرسة"."""


async def answer_query(query: str, db: Session, school_id: int, k: int = 6) -> dict[str, Any]:
    """Production RAG entry point — isolated and dynamic."""
    results = await retrieve_top_k(query, db, school_id=school_id, k=k)

    if not results:
        return {
            "answer": "لا تتوفر مستندات أو أدلة مرفوعة حالياً لهذه المدرسة في قاعدة المعرفة الذكية.",
            "sources": [],
        }
        
    chunks = [doc for doc, _ in results]
    distances = [dist for _, dist in results]

    context_block = "\n\n---\n\n".join([doc.content for doc in chunks])
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user", "content": f"النصوص المرجعية المتاحة:\n{context_block}\n\nالسؤال: {query}"},
    ]

    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.0,
    )
    answer = response.choices[0].message.content

    sources = [
        {
            "id": doc.id,
            "source": (doc.doc_metadata or {}).get("source", "unknown"),
            "chunk_index": (doc.doc_metadata or {}).get("chunk_index"),
            "distance": round(dist, 4),
        }
        for doc, dist in zip(chunks, distances)
    ]

    return {"answer": answer, "sources": sources}


def list_ingested_sources(db: Session) -> list[dict[str, Any]]:
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