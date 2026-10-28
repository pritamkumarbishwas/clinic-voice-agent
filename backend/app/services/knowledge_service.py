import asyncio
import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.database import clinic_knowledge, doctors
from app.services.embedding_service import (
    RagUnavailableError,
    cosine_similarity,
    embed_texts,
    rag_available,
)

logger = logging.getLogger("clinic-knowledge")

KnowledgeCategory = Literal[
    "general",
    "services",
    "policies",
    "directions",
    "preparation",
    "doctors",
    "other",
]
KNOWLEDGE_CATEGORIES = (
    "general",
    "services",
    "policies",
    "directions",
    "preparation",
    "doctors",
    "other",
)
MAX_CONTENT_CHARS = 50_000


class KnowledgeDocumentInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=200)
    category: KnowledgeCategory = "general"
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    active: bool = True

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return " ".join((value or "").split())

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = "\n".join(
            " ".join(line.split()) for line in (value or "").splitlines()
        ).strip()
        if not cleaned:
            raise ValueError("Knowledge content cannot be empty")
        return cleaned


class KnowledgeDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: KnowledgeCategory | None = None
    content: str | None = Field(
        default=None, min_length=1, max_length=MAX_CONTENT_CHARS
    )
    active: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = "\n".join(
            " ".join(line.split()) for line in value.splitlines()
        ).strip()
        if not cleaned:
            raise ValueError("Knowledge content cannot be empty")
        return cleaned


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return " ".join((value or "").split())


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValueError("Invalid knowledge document id") from exc


def _content_hash(title: str, category: str, content: str) -> str:
    payload = f"{title}\n{category}\n{content}".encode()
    return hashlib.sha256(payload).hexdigest()


def chunk_text(
    text: str,
    *,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    max_chars = max_chars or settings.rag_chunk_chars
    overlap = overlap if overlap is not None else settings.rag_chunk_overlap
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        if end < len(cleaned):
            window = cleaned[start:end]
            candidates = [
                window.rfind(". "),
                window.rfind("? "),
                window.rfind("! "),
                window.rfind("; "),
            ]
            break_at = max(candidates)
            if break_at >= max_chars // 2:
                end = start + break_at + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        next_start = max(0, end - overlap)
        start = next_start if next_start > start else end
    return chunks


async def _index_document(
    title: str,
    category: str,
    content: str,
) -> dict:
    if not rag_available():
        raise RagUnavailableError(
            "RAG is not configured. Set OPENAI_API_KEY and RAG_ENABLED=true."
        )

    chunks = chunk_text(content)
    if not chunks:
        raise ValueError("Knowledge content cannot be empty")

    inputs = [f"{title}\n{chunk}" for chunk in chunks]
    embeddings = await embed_texts(inputs)
    if len(embeddings) != len(chunks):
        raise RagUnavailableError(
            "The embedding provider returned an incomplete result."
        )

    return {
        "chunks": [
            {"text": chunk, "embedding": embedding}
            for chunk, embedding in zip(chunks, embeddings)
        ],
        "chunk_count": len(chunks),
        "embedding_model": settings.openai_embedding_model,
        "content_hash": _content_hash(title, category, content),
        "updated_at": datetime.now(timezone.utc),
    }


def serialize_document(document: dict) -> dict:
    updated_at = document.get("updated_at")
    created_at = document.get("created_at")
    return {
        "knowledge_id": str(document.get("_id", "")),
        "title": document.get("title", ""),
        "category": document.get("category", "general"),
        "content": document.get("content", ""),
        "active": bool(document.get("active", True)),
        "chunk_count": int(document.get("chunk_count", 0)),
        "embedding_model": document.get("embedding_model", ""),
        "created_at": (
            created_at.isoformat()
            if isinstance(created_at, datetime)
            else None
        ),
        "updated_at": (
            updated_at.isoformat()
            if isinstance(updated_at, datetime)
            else None
        ),
    }


async def list_documents() -> list[dict]:
    cursor = clinic_knowledge.find(
        {},
        {
            "chunks": 0,
        },
    ).sort("updated_at", -1)
    return [serialize_document(document) async for document in cursor]


async def create_document(payload: KnowledgeDocumentInput) -> dict:
    index = await _index_document(
        payload.title, payload.category, payload.content
    )
    now = datetime.now(timezone.utc)
    document = {
        "title": payload.title,
        "category": payload.category,
        "content": payload.content,
        "active": payload.active,
        "created_at": now,
        **index,
    }
    result = await clinic_knowledge.insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_document(document)


async def update_document(
    knowledge_id: str,
    payload: KnowledgeDocumentUpdate,
) -> dict:
    object_id = _object_id(knowledge_id)
    existing = await clinic_knowledge.find_one({"_id": object_id})
    if existing is None:
        raise LookupError("Knowledge document not found")

    updates = payload.model_dump(exclude_unset=True)
    title = updates.get("title", existing.get("title", ""))
    category = updates.get("category", existing.get("category", "general"))
    content = updates.get("content", existing.get("content", ""))
    new_hash = _content_hash(title, category, content)
    needs_index = (
        new_hash != existing.get("content_hash")
        or not existing.get("chunks")
    )

    if needs_index:
        index = await _index_document(title, category, content)
        updates.update(index)
    else:
        updates["updated_at"] = datetime.now(timezone.utc)

    await clinic_knowledge.update_one(
        {"_id": object_id},
        {"$set": updates},
    )
    document = await clinic_knowledge.find_one({"_id": object_id})
    return serialize_document(document or {})


async def delete_document(knowledge_id: str) -> None:
    object_id = _object_id(knowledge_id)
    result = await clinic_knowledge.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise LookupError("Knowledge document not found")


def extract_upload_text(filename: str, data: bytes) -> str:
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    if suffix in {"txt", "md", "markdown"}:
        return data.decode("utf-8-sig", errors="replace")

    if suffix != "pdf":
        raise ValueError("Only .txt, .md, and .pdf files are supported")

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support is not installed") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > settings.rag_max_pdf_pages:
            raise ValueError(
                f"PDF has too many pages (maximum {settings.rag_max_pdf_pages})"
            )
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages).strip()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read the PDF file") from exc

    if not text:
        raise ValueError("The uploaded file did not contain readable text")
    return text


def _knowledge_results(
    query_embedding: list[float],
    documents: list[dict],
    *,
    top_k: int,
    min_score: float,
) -> list[dict]:
    results: list[dict] = []
    for document in documents:
        title = document.get("title", "")
        category = document.get("category", "general")
        for chunk in document.get("chunks", []):
            embedding = chunk.get("embedding") or []
            score = cosine_similarity(query_embedding, embedding)
            if score < min_score:
                continue
            results.append(
                {
                    "source": "knowledge",
                    "title": title,
                    "category": category,
                    "text": chunk.get("text", ""),
                    "score": round(score, 4),
                }
            )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


async def search_knowledge(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[dict]:
    cleaned = " ".join((query or "").split())
    if not cleaned:
        return []

    top_k = top_k or settings.rag_top_k
    min_score = (
        settings.rag_min_score if min_score is None else min_score
    )
    query_embedding = (await embed_texts([cleaned]))[0]

    async def _load_documents() -> list[dict]:
        return [
            document
            async for document in clinic_knowledge.find(
                {"active": True},
                {"title": 1, "category": 1, "chunks": 1},
            ).limit(settings.rag_max_documents)
        ]

    async def _load_doctors() -> list[dict]:
        return [
            doctor
            async for doctor in doctors.find(
                {
                    "active": True,
                    "bio": {"$nin": [None, ""]},
                    "bio_embedding": {"$exists": True, "$ne": None},
                },
                {
                    "name": 1,
                    "specialty": 1,
                    "bio": 1,
                    "bio_embedding": 1,
                },
            ).limit(100)
        ]

    documents, doctor_docs = await asyncio.gather(
        _load_documents(),
        _load_doctors(),
    )
    results = _knowledge_results(
        query_embedding,
        documents,
        top_k=top_k,
        min_score=min_score,
    )

    doctor_results: list[dict] = []
    for doctor in doctor_docs:
        score = cosine_similarity(
            query_embedding, doctor.get("bio_embedding") or []
        )
        if score < min_score:
            continue
        name = doctor.get("name", "")
        specialty = doctor.get("specialty", "")
        label = f"{name} ({specialty})" if specialty else name
        doctor_results.append(
            {
                "source": "doctor",
                "title": f"Doctor profile: {name}",
                "category": "doctors",
                "text": f"{label}. {doctor.get('bio', '')}".strip(),
                "score": round(score, 4),
            }
        )

    combined = sorted(
        results + doctor_results,
        key=lambda item: item["score"],
        reverse=True,
    )
    return combined[:top_k]


def knowledge_status() -> dict:
    return {
        "enabled": settings.rag_enabled,
        "available": rag_available(),
        "embedding_model": settings.openai_embedding_model,
    }


def is_valid_category(value: str) -> bool:
    return value in KNOWLEDGE_CATEGORIES


def normalize_category(value: str) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned if is_valid_category(cleaned) else "general"


def guess_title_from_filename(filename: str) -> str:
    stem = re.sub(r"\.[^.]+$", "", filename or "").strip()
    title = re.sub(r"[_-]+", " ", stem)
    return " ".join(title.split())[:200] or "Uploaded clinic knowledge"
