import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import CurrentUser, require_admin
from app.config import settings
from app.services.embedding_service import RagUnavailableError
from app.services.knowledge_service import (
    KnowledgeDocumentInput,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    create_document,
    delete_document,
    extract_upload_text,
    guess_title_from_filename,
    knowledge_status,
    list_documents,
    normalize_category,
    search_knowledge,
    update_document,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    if file.size is not None and file.size > settings.rag_max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large. Maximum size is "
                f"{settings.rag_max_upload_bytes} bytes."
            ),
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.rag_max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    "File is too large. Maximum size is "
                    f"{settings.rag_max_upload_bytes} bytes."
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("")
async def read_knowledge(_: CurrentUser = Depends(require_admin)):
    return {
        "items": await list_documents(),
        **knowledge_status(),
    }


@router.post("")
async def create_knowledge_endpoint(
    payload: KnowledgeDocumentInput,
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await create_document(payload)
    except RagUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/{knowledge_id}")
async def update_knowledge_endpoint(
    knowledge_id: str,
    payload: KnowledgeDocumentUpdate,
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await update_document(knowledge_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RagUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{knowledge_id}")
async def delete_knowledge_endpoint(
    knowledge_id: str,
    _: CurrentUser = Depends(require_admin),
):
    try:
        await delete_document(knowledge_id)
        return {"ok": True}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search")
async def search_knowledge_endpoint(
    payload: KnowledgeSearchRequest,
    _: CurrentUser = Depends(require_admin),
):
    try:
        return {
            "results": await search_knowledge(
                payload.query, top_k=payload.top_k
            ),
            **knowledge_status(),
        }
    except RagUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/upload")
async def upload_knowledge_endpoint(
    file: UploadFile = File(...),
    title: str = Form(""),
    category: str = Form("general"),
    active: bool = Form(True),
    _: CurrentUser = Depends(require_admin),
):
    try:
        data = await _read_upload(file)
        content = await asyncio.to_thread(
            extract_upload_text, file.filename or "", data
        )
        payload = KnowledgeDocumentInput(
            title=title.strip()
            or guess_title_from_filename(file.filename or ""),
            category=normalize_category(category),
            content=content,
            active=active,
        )
        return await create_document(payload)
    except RagUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()
