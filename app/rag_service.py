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
    """Extract all text from PDF bytes."""
    reader = PdfReader(BytesIO(pdf_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text.strip():
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


# ============================================================
# تعديل دالة التقطيع: حقن اسم الملف داخل النص لحفظ السياق
# ============================================================
def chunk_document(text: str, source: str) -> list[dict[str, Any]]:
    """Split text into chunks and inject source name at the top of each chunk."""
    raw_chunks = _splitter.split_text(text)
    total = len(raw_chunks)
    processed_chunks = []

    for i, chunk in enumerate(raw_chunks):
        # حقن اسم المصدر في بداية النص المخرن والمُولد له الـ embedding
        enriched_content = f"المستند المرجعي المعتمد: {source}\nالنص التفصيلي: {chunk}"
        processed_chunks.append({
            "content": enriched_content,
            "metadata": {
                "source": source,
                "chunk_index": i,
                "total_chunks": total,
            },
        })
    return processed_chunks


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using HuggingFace Inference API."""
    if not texts:
        return []
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": texts, "options": {"wait_for_model": True}}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(HF_EMBEDDING_URL, headers=headers, json=payload)
        response.raise_for_status()
        embeddings = response.json()
    return embeddings


async def ingest_document(pdf_bytes: bytes, filename: str, db: Session) -> int:
    """Full ingest pipeline: PDF → chunks with context injection → embeddings → DB."""
    text = extract_text_from_pdf_bytes(pdf_bytes)
    if not text.strip():
        raise ValueError(f"No text extracted from {filename!r}.")

    chunks = chunk_document(text, source=filename)
    if not chunks:
        raise ValueError(f"Chunking produced 0 chunks for {filename!r}.")

    contents = [c["content"] for c in chunks]
    embeddings = await embed_texts(contents)

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
# تعديل دالة الاسترجاع: دعم الفلترة الذكية لمنع التداخل
# ============================================================
async def retrieve_top_k(
    query: str,
    db: Session,
    k: int = 6,
    source_filter: Optional[str] = None,
) -> list[tuple[Document, float]]:
    """Retrieve top-K similar chunks with optional strictly enforced source metadata filtering."""
    query_embeddings = await embed_texts([query])
    query_vec = query_embeddings[0]

    distance = Document.embedding.cosine_distance(query_vec).label("distance")
    stmt = select(Document, distance)

    # إذا كان هناك فلتر محدد للملف، ابحث بداخله هو فقط مجبراً قاعدة البيانات على تصفية الباقي
    if source_filter:
        stmt = stmt.where(Document.doc_metadata["source"].astext == source_filter)
        
    stmt = stmt.order_by(distance.asc()).limit(k)
    results = db.execute(stmt).all()
    return [(row[0], float(row[1])) for row in results]


# ============================================================
# نظام الـ Prompt المطور لمواجهة التشتت والدقة العالية
# ============================================================
RAG_SYSTEM_PROMPT = """أنت خبير تدقيق تكنولوجي مستند إلى بيانات صارمة وحتمية. مهمتك الإجابة عن أسئلة المستخدمين بناءً على النصوص المرجعية (Context) المرفقة فقط.

القواعد الحتمية:
1. اقرأ كل قطعة نصية مرجعية بعناية؛ حيث تبدأ كل قطعة بـ (المستند المرجعي المعتمد).
2. انتبه بشدة لاسم المستند؛ لا تخلط أبداً بين بيانات مدرسة "ابدأ" (ebdaa_badr_rag_v3.pdf) ومدرسة "أرابكوميد" (arabcomed_obour_rag_v3.pdf).
3. إذا كان سؤال المستخدم عن مدرسة "ابدأ"، اعتمد فقط وفقط على القطع التي تخص مدرسة ابدأ، وتجاهل تماماً أي معلومات من مدرسة أخرى حتى لو تشابهت العناوين.
4. أجب عن الأسئلة بدقة كاملة مستخرجاً الشروط، الميزات، أو الأسئلة الشائعة كما وردت في أواخر أو أجزاء المستندات.
5. إذا لم تجد الإجابة صريحة في النص المرفق، قل: "عذراً، لا تتوفر معلومات دقيقة حول هذا السؤال في المستند المرجعي الخاص بهذه المدرسة."
"""

def build_augmented_prompt(query: str, chunks: list[Document]) -> list[dict[str, str]]:
    context_parts = []
    for doc in chunks:
        context_parts.append(doc.content)

    context_block = "\n\n---\n\n".join(context_parts)
    user_content = f"النصوص المرجعية المتاحة:\n{context_block}\n\nالسؤال: {query}"

    return [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# ============================================================
# دالة الإجابة النهائية مع الفلترة التلقائية الذكية
# ============================================================
async def answer_query(
    query: str,
    db: Session,
    k: int = 6,
) -> dict[str, Any]:
    """Full RAG loop with intelligent auto-routing based on query keywords."""
    
    # فلترة تلقائية ذكية: إذا سأل عن "ابدأ" ابحث في ملفها فقط، وإذا سأل عن "أرابكوميد" أو "مستحضرات" ابحث في ملفها فقط.
    # هذا يمنع اكتساح ملف لأخر نهائياً ويحل مشكلة الأسئلة في أواخر الملفات.
    source_filter = None
    if "ابدأ" in query or "ابدا" in query:
        source_filter = "ebdaa_badr_rag_v3.pdf"
    elif "أرابكوميد" in query or "ارابكوميد" in query or "مستحضرات" in query or "دوائية" in query:
        source_filter = "arabcomed_obour_rag_v3.pdf"

    # استدعاء الاسترجاع بالفلتر الذكي
    results = await retrieve_top_k(query, db, k=k, source_filter=source_filter)

    if not results:
        return {
            "answer": "لم أجد نصوصاً مطابقة في قاعدة البيانات أو يرجى رفع الملفات أولاً.",
            "sources": [],
        }
        
    chunks = [doc for doc, _ in results]
    distances = [dist for _, dist in results]

    messages = build_augmented_prompt(query, chunks)

    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.0, # صفر لتثبيت النموذج ومنع التشتت والـ Hallucination تماماً
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