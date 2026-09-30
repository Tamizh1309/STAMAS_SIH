"""Tender document ingestion over PostgreSQL: validation, safe file storage,
extraction, metadata + text + clauses persisted in Neon.

Uploaded bytes stay on disk under backend/storage/documents/ — never inside
frontend/ and never committed (see .gitignore).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.errors import ApiError
from ..db.repositories import AnalysisRepository, ClauseRepository, DocumentRepository, TenderRepository
from . import clause_service, document_extractors
from .document_extractors import ExtractionError
from ..schemas.document import DocumentStatus

log = logging.getLogger("stamas.documents")

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}
MIME_BY_EXT = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


def max_bytes() -> int:
    return settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024


def storage_dir() -> Path:
    raw = settings.DOCUMENT_STORAGE_PATH
    p = Path(raw)
    if not p.is_absolute():
        # resolve relative to the backend/ directory (parent of app/)
        backend_dir = Path(__file__).resolve().parents[2]
        p = backend_dir / raw
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception as exc:
        log.warning("Storage directory %s unavailable (%s), falling back to /tmp/storage/documents", p, exc)
        fallback = Path("/tmp/storage/documents")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def safe_server_filename(original: str, doc_id: str, ext: str) -> str:
    stem = Path(original).name
    stem = _SAFE_STEM_RE.sub("_", stem)
    stem = stem[:60].strip("._") or "document"
    return f"{doc_id}__{stem}.{ext}" if not stem.endswith(f".{ext}") else f"{doc_id}__{stem}"


async def _require_tender(session: AsyncSession, tender_id: str) -> dict[str, Any]:
    tender = await TenderRepository.get_by_id(session, tender_id)
    if tender is None:
        raise ApiError(f'Tender with ID "{tender_id}" not found.', 404)
    return tender


def _validate_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError(
            f'Unsupported document type ".{ext or "?"}". Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}.',
            415,
        )
    return ext


async def ingest_file(
    session: AsyncSession, tender_id: str, filename: str, content: bytes, content_type: str | None
) -> dict[str, Any]:
    """Validate → store → extract → PROCESSED. Raises ApiError on any failure."""
    await _require_tender(session, tender_id)
    original = (filename or "").strip()
    if not original:
        raise ApiError("A filename is required for every uploaded document.", 400)
    if ".." in original or "/" in original or "\\" in original:
        # never trust client paths; keep only the basename semantics via validation
        raise ApiError("Invalid filename: path separators are not allowed.", 400)
    ext = _validate_extension(original)
    if not content:
        raise ApiError(f'"{original}" is empty. Upload a non-empty document.', 400)
    if len(content) > max_bytes():
        raise ApiError(
            f'"{original}" exceeds the {settings.MAX_DOCUMENT_SIZE_MB} MB per-file limit.',
            413,
        )

    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    server_name = safe_server_filename(original, doc_id, ext)
    dest = storage_dir() / server_name
    # belt & braces: ensure the resolved path stays inside the storage dir
    if dest.resolve().parent != storage_dir().resolve():
        raise ApiError("Invalid filename: storage path escape detected.", 400)

    meta = await DocumentRepository.create(
        session,
        document_id=doc_id,
        tender_id=tender_id,
        filename=Path(original).name,
        file_type=ext,
        mime_type=content_type or MIME_BY_EXT[ext],
        file_size=len(content),
        storage_path=str(dest),
        status=DocumentStatus.UPLOADED.value,
    )

    try:
        dest.write_bytes(content)
    except OSError as exc:
        log.error("Document %s disk write failed: %s", doc_id, exc)
        await DocumentRepository.update(
            session, doc_id, status=DocumentStatus.FAILED.value, error_message="Server storage failure."
        )
        raise ApiError("Document storage failure. Try again.", 500)

    # synchronous extraction (demo-acceptable); isolated for future backgrounding
    await DocumentRepository.update(session, doc_id, status=DocumentStatus.PROCESSING.value)
    try:
        text, count = document_extractors.extract_text(ext, dest)
    except ExtractionError as exc:
        log.warning("Document %s extraction failed: %s", doc_id, exc)
        updated = await DocumentRepository.update(
            session, doc_id, status=DocumentStatus.FAILED.value, error_message=str(exc)
        )
        return updated or meta
    except Exception:  # never leak internals
        log.exception("Document %s unexpected extraction error", doc_id)
        updated = await DocumentRepository.update(
            session, doc_id, status=DocumentStatus.FAILED.value, error_message="Document processing failure."
        )
        return updated or meta

    try:
        raw_clauses = clause_service.extract_clauses(
            text, source_document_id=doc_id, source_document_name=meta["fileName"]
        )
    except Exception as exc:
        log.warning("Document %s clause extraction failed: %s", doc_id, exc)
        raw_clauses = []
    namespaced = []
    for c in raw_clauses:
        item = dict(c)
        item["id"] = f"{doc_id}-{c.get('id', 'clause')}"
        namespaced.append(item)
    await ClauseRepository.create_many(session, tender_id, doc_id, namespaced)

    updated = await DocumentRepository.update(
        session,
        doc_id,
        status=DocumentStatus.PROCESSED.value,
        extracted_text=text,
        extracted_text_length=len(text),
        page_count=count,
        error_message=None,
    )
    return updated or meta


async def list_documents(session: AsyncSession, tender_id: str) -> list[dict[str, Any]]:
    await _require_tender(session, tender_id)
    return await DocumentRepository.list_by_tender(session, tender_id)


async def get_document(session: AsyncSession, tender_id: str, document_id: str) -> dict[str, Any]:
    await _require_tender(session, tender_id)
    meta = await DocumentRepository.get(session, tender_id, document_id)
    if meta is None:
        raise ApiError(f'Document "{document_id}" not found for this tender.', 404)
    return meta


async def get_document_text(
    session: AsyncSession, tender_id: str, document_id: str, max_chars: int = 20000
) -> tuple[dict[str, Any], str, bool]:
    meta = await get_document(session, tender_id, document_id)
    if meta["status"] != DocumentStatus.PROCESSED.value:
        reason = meta.get("error") or "Text extraction did not complete for this document."
        raise ApiError(f"Extracted text unavailable: {reason}", 404)
    row_text = await DocumentRepository.get_text(session, tender_id, document_id, max_chars)
    if row_text is None:
        raise ApiError("Extracted text unavailable: text record missing.", 404)
    _, text, truncated = row_text
    return meta, text, truncated


async def rename_document(
    session: AsyncSession, tender_id: str, document_id: str, file_name: str
) -> dict[str, Any]:
    """Rename a document's display filename. Extension must stay the same."""
    meta = await get_document(session, tender_id, document_id)  # 404 if missing/mismatched
    new_name = (file_name or "").strip()
    if not new_name or len(new_name) > 255:
        raise ApiError("A new filename of 1–255 characters is required.", 422)
    if "/" in new_name or "\\" in new_name or ".." in new_name:
        raise ApiError("Invalid filename: path separators are not allowed.", 422)
    old_ext = Path(meta["fileName"]).suffix.lower()
    new_ext = Path(new_name).suffix.lower()
    if not new_ext or new_ext != old_ext:
        raise ApiError(
            f"Rename must keep the original extension ({old_ext or meta['fileType']}).", 422
        )
    updated = await DocumentRepository.update(session, document_id, filename=new_name)
    if updated is None:
        raise ApiError(f'Document "{document_id}" not found for this tender.', 404)
    return updated


async def delete_document(session: AsyncSession, tender_id: str, document_id: str) -> str:
    meta = await get_document(session, tender_id, document_id)  # 404 if missing/mismatched
    deleted = await DocumentRepository.delete(session, tender_id, document_id)
    if deleted is None:
        raise ApiError(f'Document "{document_id}" not found for this tender.', 404)
    storage_path = deleted.pop("_storage_path", "")
    if storage_path:
        try:
            Path(storage_path).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not remove stored file for %s: %s", document_id, exc)
    # Opportunity snapshots were computed from a doc set that just changed.
    await AnalysisRepository.delete_stale_for_document(session, tender_id, document_id)
    return deleted["fileName"]


async def get_clauses_for_tender(session: AsyncSession, tender_id: str) -> list[dict[str, Any]]:
    await _require_tender(session, tender_id)
    return await ClauseRepository.list_by_tender(session, tender_id)


async def find_clause(
    session: AsyncSession, tender_id: str, clause_id: str
) -> dict[str, Any] | None:
    return await ClauseRepository.find(session, tender_id, clause_id)


async def run_opportunity_analysis(
    session: AsyncSession, tender_id: str, bidder_name: str | None = None
) -> dict[str, Any]:
    """Gather PROCESSED doc texts → Gemini opportunity analysis → persist."""
    from . import gemini_service  # deferred: gemini_service never imports document_service

    tender = await _require_tender(session, tender_id)
    docs = [
        m for m in await DocumentRepository.list_by_tender(session, tender_id)
        if m["status"] == DocumentStatus.PROCESSED.value
    ]
    if not docs:
        raise ApiError("No processed documents available for analysis on this tender.", 404)
    texts: list[tuple[str, str]] = []
    for meta in docs:
        row_text = await DocumentRepository.get_text(session, tender_id, meta["id"], max_chars=6000)
        if row_text is not None:
            _, text, _ = row_text
            texts.append((meta["fileName"], text))
    if not texts:
        raise ApiError("Processed documents contain no extractable text.", 404)
    bidder = None
    if bidder_name:
        bidder = next((b for b in tender.get("bidders", []) if b.get("name") == bidder_name), None)
        if bidder is None:
            bidder = {"name": bidder_name}
    outcome = gemini_service.analyze_tender_opportunity(tender, texts, bidder)
    record = await AnalysisRepository.save(
        session,
        analysis_id=f"an-{uuid.uuid4().hex[:12]}",
        tender_id=tender_id,
        document_id=docs[0]["id"] if len(docs) == 1 else None,
        kind="opportunity",
        result=outcome["result"],
        engine=outcome["engine"],
    )
    return record


async def latest_analysis(
    session: AsyncSession, tender_id: str, kind: str = "opportunity"
) -> dict[str, Any] | None:
    await _require_tender(session, tender_id)
    return await AnalysisRepository.latest(session, tender_id, kind)
