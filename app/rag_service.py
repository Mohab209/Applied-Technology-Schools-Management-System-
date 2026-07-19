"""RAG service — chunking, embedding, storing, retrieving, generating."""
import os
from io import BytesIO
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.llm_service import PROVIDERS
from app.models import Document

load_dotenv()

# ============================================================
# Reuse the Groq client + model from llm_service
# ============================================================
_groq_config = PROVIDERS["groq"]
groq_client = _groq_config["client"]
GROQ_MODEL = _groq_config["model"]

# ============================================================
# HuggingFace Inference API setup — MULTILINGUAL Embeddings
# ============================================================
HF_TOKEN = os.getenv("HF_TOKEN")
# تم استبداله بنموذج قوي جداً ومتعدد اللغات يدعم العربية بكفاءة خارقة
HF_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HF_EMBEDDING_URL = f"https://router.huggingface.co/hf-inference/models/{HF_EMBEDDING_MODEL}/pipeline/feature-extraction"
# تذكر تغيير أبعاد العمود في قاعدة البيانات (Vector Dimension) إلى 384 إذا لم تكن كذلك
EMBEDDING_DIM = 384

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN not found in .env — required for embeddings")

# ============================================================
# Chunking config — Optimized for Arabic Context and Knowledge Base
# ============================================================
# تم رفع الحجم لتصبح الفقرة والأسئلة الشائعة كاملة داخل نفس الـ Chunk
CHUNK_SIZE = 2000 
CHUNK_OVERLAP = 200

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    # ترتيب الفواصل المخصص للعربية لضمان عدم قطع جملة شرطية
    separators=["\n\n", "\n", "؟ ", "، ", ". ", " ", ""],
)


# ============================================================
# PDF extraction
# ============================================================
def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes."""
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
    """Split text into chunks with metadata attached."""
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
    """Embed a batch of texts using HuggingFace Inference API."""
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
# Ingest: PDF → chunks → embeddings → Database
# ============================================================
async def ingest_document(
    pdf_bytes: bytes,
    filename: str,
    db: Session,
) -> int:
    """Full ingest pipeline: PDF → chunks → embeddings → DB."""
    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        raise ValueError(
            f"No text extracted from {filename!r}. "
            "The PDF may be scanned images — OCR is not supported."
        )

    chunks = chunk_document(text, source=filename)
    if not chunks:
        raise ValueError(f"Chunking produced 0 chunks for {filename!r}.")

    contents = [c["content"] for c in chunks]
    embeddings = await embed_texts(contents)

    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: got {len(embeddings)} for {len(chunks)} chunks"
        )

    docs = [
        Document(
            content=chunk["content"],
            embedding=embedding,
            doc_metadata=chunk["metadata"],
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    db.add_all(docs)
    db.commit()

    return len(docs)


# ============================================================
# Retrieval: query → top-K similar chunks
# ============================================================
async def retrieve_top_k(
    query: str,
    db: Session,
    k: int = 6,
) -> list[tuple[Document, float]]:
    """Retrieve top-K most similar chunks using fixed cosine_distance."""
    # 1. توليد الـ Embedding الخاص بالسؤال
    query_embeddings = await embed_texts([query])
    query_vec = query_embeddings[0]

    # 2. حساب المسافة (كلما قلّت المسافة زاد التشابه الدلالي)
    distance = Document.embedding.cosine_distance(query_vec).label("distance")
    
    # 3. استخدام الترتيب التصاعدي .asc() لجلب القطع الأقرب في الصدارة
    stmt = (
        select(Document, distance)
        .order_by(distance.asc()) 
        .limit(k)
    )

    results = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in results]


# ============================================================
# Prompt building for RAG — Optimized for Arabic Response
# ============================================================
RAG_SYSTEM_PROMPT = """أنت مساعد ذكي ومحترف. مهمتك هي الإجابة عن أسئلة المستخدمين بدقة شديدة وبناءً **فقط** على السياق والنصوص المقدمة إليك.

القواعد الصارمة:
1. استخدم المعلومات الواردة في السياق (Context) فقط للإجابة.
2. إذا كان السياق لا يحتوي على معلومات كافية واضحة ومباشرة للإجابة عن السؤال، قل نصاً وبدون زيادة: 
   "عذراً، لا تتوفر لدي معلومات كافية في المستندات المرفقة للإجابة عن هذا السؤال."
3. لا تستخدم أي معلومات خارجية أو استنتاجات لم تذكر صراحة.
4. اذكر اسم المصدر دائماً في نهاية إجابتك (مثال: بناءً على ملف sample.pdf...).
5. صغ الإجابة باللغة العربية الفصحى بشكل دقيق ومختصر ومباشر.
"""


def build_augmented_prompt(query: str, chunks: list[Document]) -> list[dict[str, str]]:
    """Build the OpenAI-format messages list with context injected."""
    context_parts = []
    for doc in chunks:
        meta = doc.doc_metadata or {}
        source = meta.get("source", "unknown")
        idx = meta.get("chunk_index", "?")
        context_parts.append(f"[المصدر: {source}, القطعة: {idx}]\n{doc.content}")

    context_block = "\n\n".join(context_parts)

    user_content = (
        f"النصوص المرجعية (Context):\n{context_block}\n\n"
        f"السؤال المطروح: {query}"
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
    k: int = 6,
) -> dict[str, Any]:
    """Full RAG loop: retrieve top-K, build prompt, call LLM, return answer + sources."""
    results = await retrieve_top_k(query, db, k=k)

    if not results:
        return {
            "answer": "لا توجد مستندات في قاعدة المعرفة حالياً. يرجى رفع ملف PDF أولاً.",
            "sources": [],
        }
        
    chunks = [doc for doc, _ in results]
    distances = [dist for _, dist in results]

    messages = build_augmented_prompt(query, chunks)

    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,  # خفض الحرارة لـ 0.1 لضمان أعلى دقة ومنع التأليف
    )
    answer = response.choices[0].message.content

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