"""RAG service — chunking, embedding, storing, retrieving, generating."""
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
EMBEDDING_DIM = 384

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in .env — required for embeddings")

# إعدادات حجم Chunks مثالية للموسوعات المحدثة
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", "؟ ", "، ", ". ", " ", ""],
)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def chunk_document(text: str, source: str) -> list[dict[str, Any]]:
    raw_chunks = _splitter.split_text(text)
    total = len(raw_chunks)
    return [
        {
            "content": f"المستند المرجعي: {source}\nالمحتوى التفصيلي:\n{chunk}",
            "metadata": {
                "source": source,
                "chunk_index": i + 1,
                "total_chunks": total,
            },
        }
        for i, chunk in enumerate(raw_chunks)
    ]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": texts, "options": {"wait_for_model": True}}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(HF_EMBEDDING_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def ingest_document(pdf_bytes: bytes, filename: str, school_id: int, db: Session) -> int:
    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        raise ValueError(f"No readable text found in {filename!r}.")

    chunks = chunk_document(text, source=filename)
    contents = [c["content"] for c in chunks]
    embeddings = await embed_texts(contents)

    docs = [
        Document(
            content=chunk["content"],
            embedding=embedding,
            doc_metadata=chunk["metadata"],
            school_id=school_id
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    db.add_all(docs)
    db.commit()
    return len(docs)


async def retrieve_top_k(query: str, db: Session, school_id: int, k: int = 5) -> list[tuple[Document, float]]:
    query_embeddings = await embed_texts([query])
    query_vec = query_embeddings[0]

    distance = Document.embedding.cosine_distance(query_vec).label("distance")
    
    stmt = (
        select(Document, distance)
        .where(Document.school_id == school_id)
        .order_by(distance.asc())
        .limit(k)
    )

    results = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in results]


def build_augmented_prompt(query: str, chunks: list[Document]) -> list[dict[str, str]]:
    context_block = "\n\n---\n\n".join([doc.content for doc in chunks])
    
    system_instruction = (
        "أنت مستشار ذكي خبير وموثوق لمدارس التكنولوجيا التطبيقية في مصر.\n"
        "مهمتك هي الإجابة على أسئلة المستخدمين بدقة وبناءً على النصوص المرجعية الرسمية المرفقة فقط.\n"
        "قواعد صارمة:\n"
        "1. اعتمد فقط على المعلومات المذكورة في المستند المرجعي المرفق.\n"
        "2. إذا لم تكن الإجابة موجودة في النص، قل بدقة: 'عذراً، لا تتوفر معلومات تفصيلية دقيقة حول هذا السؤال في الدليل الحالي المرفوع للمدرسة.'\n"
        "3. لا تقم باختلاق أو تخمين أي حقول أو شروط غير موجودة صراحة."
    )
    
    user_content = (
        f"المستندات الرسمية المسترجعة:\n{context_block}\n\n"
        f"السؤال: {query}\n"
        f"الإجابة المعتمدة والمفصلة:"
    )
    
    return [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content}
    ]


async def answer_query(query: str, db: Session, school_id: int, k: int = 5) -> dict[str, Any]:
    results = await retrieve_top_k(query, db, school_id=school_id, k=k)

    if not results:
        return {
            "answer": "لا تتوفر كتب شروط أو أدلة مرفوعة حالياً لهذه المدرسة في قاعدة المعرفة، يرجى تزويد النظام بملف دليل المدرسة أولاً.",
            "sources": [],
        }
        
    chunks = [doc for doc, _ in results]
    distances = [dist for _, dist in results]

    messages = build_augmented_prompt(query, chunks)

    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.0,
    )
    answer = response.choices[0].message.content

    # بناء قائمة المصادر بشكل صارم ومفلتر (اسم الملف + رقم الجزء + مقتطف النص)
    sources = [
        {
            "source": (doc.doc_metadata or {}).get("source"),
            "chunk_index": (doc.doc_metadata or {}).get("chunk_index"),
            "snippet": doc.content.replace(f"المستند المرجعي: {(doc.doc_metadata or {}).get('source')}\nالمحتوى التفصيلي:\n", "")[:200] + "..."
        }
        for doc, dist in zip(chunks, distances)
        if doc.doc_metadata and doc.doc_metadata.get("source") and doc.doc_metadata.get("chunk_index") is not None
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