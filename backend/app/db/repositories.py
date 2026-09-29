"""Repository layer — all SQL lives here.

Each repository works on an injected AsyncSession and returns plain dicts in
the exact shapes the previous in-memory store produced, so services, routes,
Gemini and the React frontend keep working unchanged.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ApiError
from .models import AnalysisRow, ClauseRow, DocumentRow, TenderRow

log = logging.getLogger("stamas.db.repo")


def _db_error(action: str, exc: Exception) -> ApiError:
    if isinstance(exc, IntegrityError):
        return ApiError(
            f"Duplicate record while {action}: a tender with this number already exists.", 409
        )
    log.warning("Database error while %s: %s", action, type(exc).__name__)
    return ApiError("Database unavailable. Try again shortly.", 503)


# Neon free-tier compute suspends when idle; the first query afterwards can
# hit a TLS/DNS stall. Retry reads once (writes are never retried, so a
# half-committed insert can never duplicate).
_TRANSIENT_ERRORS = (TimeoutError, OSError, DBAPIError, OperationalError, InterfaceError)
F = TypeVar("F", bound=Callable[..., Any])


def _retry_read(fn: F) -> F:
    @functools.wraps(fn)
    async def wrapper(session: AsyncSession, *args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(session, *args, **kwargs)
        except ApiError:
            raise
        except _TRANSIENT_ERRORS as exc:
            log.info("Transient DB error (%s), retrying read once", type(exc).__name__)
            try:
                await session.rollback()
            except Exception:
                pass
            await asyncio.sleep(1.0)
            try:
                return await fn(session, *args, **kwargs)
            except ApiError:
                raise
            except SQLAlchemyError as exc2:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise _db_error("database operation", exc2)

    return wrapper  # type: ignore[return-value]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenderRepository:
    @staticmethod
    @_retry_read
    async def list_all(session: AsyncSession) -> list[dict[str, Any]]:
        try:
            rows = (
                await session.execute(
                    select(TenderRow).order_by(TenderRow.created_at.desc())
                )
            ).scalars().all()
            return [dict(r.data) for r in rows]
        except SQLAlchemyError as exc:
            raise _db_error("listing tenders", exc)

    @staticmethod
    @_retry_read
    async def get_by_id(session: AsyncSession, tender_id: str) -> Optional[dict[str, Any]]:
        try:
            row = await session.get(TenderRow, tender_id)
            return dict(row.data) if row is not None else None
        except SQLAlchemyError as exc:
            raise _db_error("reading tender", exc)

    @staticmethod
    @_retry_read
    async def get_by_tender_no(session: AsyncSession, tender_no: str) -> Optional[dict[str, Any]]:
        try:
            row = (
                await session.execute(
                    select(TenderRow).where(TenderRow.tender_no == tender_no)
                )
            ).scalars().first()
            return dict(row.data) if row is not None else None
        except SQLAlchemyError as exc:
            raise _db_error("reading tender", exc)

    @staticmethod
    async def create(
        session: AsyncSession,
        tender_id: str,
        tender_no: str,
        data: dict[str, Any],
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            row = TenderRow(
                id=tender_id,
                tender_no=tender_no,
                data=dict(data),
                created_at=created_at or _utcnow(),
            )
            session.add(row)
            await session.commit()
            return dict(data)
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("creating tender", exc)

    @staticmethod
    async def save(session: AsyncSession, tender_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Replace the whole tender document (bidders + stats live inside)."""
        try:
            row = await session.get(TenderRow, tender_id)
            if row is None:
                return None
            row.data = dict(data)
            await session.commit()
            return dict(data)
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("updating tender", exc)

    @staticmethod
    @_retry_read
    async def count(session: AsyncSession) -> int:
        try:
            return (
                await session.execute(select(func.count()).select_from(TenderRow))
            ).scalar_one()
        except SQLAlchemyError as exc:
            raise _db_error("counting tenders", exc)


class DocumentRepository:
    @staticmethod
    def _to_meta(row: DocumentRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "tenderId": row.tender_id,
            "fileName": row.filename,
            "fileType": row.file_type,
            "mimeType": row.mime_type,
            "size": row.file_size,
            "status": row.status,
            "uploadedAt": row.uploaded_at.isoformat() if row.uploaded_at else "",
            "extractedTextLength": row.extracted_text_length,
            "pageCount": row.page_count,
            "error": row.error_message,
        }

    @staticmethod
    @_retry_read
    async def list_by_tender(session: AsyncSession, tender_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                await session.execute(
                    select(DocumentRow)
                    .where(DocumentRow.tender_id == tender_id)
                    .order_by(DocumentRow.uploaded_at.asc())
                )
            ).scalars().all()
            return [DocumentRepository._to_meta(r) for r in rows]
        except SQLAlchemyError as exc:
            raise _db_error("listing documents", exc)

    @staticmethod
    @_retry_read
    async def get(session: AsyncSession, tender_id: str, document_id: str) -> Optional[dict[str, Any]]:
        try:
            row = await session.get(DocumentRow, document_id)
            if row is None or row.tender_id != tender_id:
                return None
            return DocumentRepository._to_meta(row)
        except SQLAlchemyError as exc:
            raise _db_error("reading document", exc)

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        document_id: str,
        tender_id: str,
        filename: str,
        file_type: str,
        mime_type: str,
        file_size: int,
        storage_path: str,
        status: str,
    ) -> dict[str, Any]:
        try:
            row = DocumentRow(
                id=document_id,
                tender_id=tender_id,
                filename=filename,
                file_type=file_type,
                mime_type=mime_type,
                file_size=file_size,
                storage_path=storage_path,
                status=status,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return DocumentRepository._to_meta(row)
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("storing document", exc)

    @staticmethod
    async def update(session: AsyncSession, document_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        try:
            row = await session.get(DocumentRow, document_id)
            if row is None:
                return None
            column_map = {
                "status": "status",
                "extracted_text": "extracted_text",
                "extracted_text_length": "extracted_text_length",
                "page_count": "page_count",
                "error_message": "error_message",
                "filename": "filename",
            }
            for key, value in fields.items():
                if key in column_map:
                    setattr(row, column_map[key], value)
            await session.commit()
            await session.refresh(row)
            return DocumentRepository._to_meta(row)
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("updating document", exc)

    @staticmethod
    async def delete(session: AsyncSession, tender_id: str, document_id: str) -> Optional[dict[str, Any]]:
        """Delete metadata (+ cascaded clauses). Returns meta incl. storage path, or None."""
        try:
            row = await session.get(DocumentRow, document_id)
            if row is None or row.tender_id != tender_id:
                return None
            meta = DocumentRepository._to_meta(row)
            storage_path = row.storage_path
            await session.delete(row)
            await session.commit()
            meta["_storage_path"] = storage_path
            return meta
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("deleting document", exc)

    @staticmethod
    @_retry_read
    async def get_text(
        session: AsyncSession, tender_id: str, document_id: str, max_chars: int = 20000
    ) -> Optional[tuple[dict[str, Any], str, bool]]:
        try:
            row = await session.get(DocumentRow, document_id)
            if row is None or row.tender_id != tender_id:
                return None
            text = row.extracted_text or ""
            if row.status != "PROCESSED" or not text:
                return None
            if len(text) > max_chars:
                return DocumentRepository._to_meta(row), text[:max_chars], True
            return DocumentRepository._to_meta(row), text, False
        except SQLAlchemyError as exc:
            raise _db_error("reading document text", exc)


class ClauseRepository:
    @staticmethod
    async def create_many(
        session: AsyncSession, tender_id: str, document_id: str, clauses: list[dict[str, Any]]
    ) -> None:
        try:
            for c in clauses:
                session.add(
                    ClauseRow(
                        id=c.get("id") or f"{document_id}-clause",
                        tender_id=tender_id,
                        document_id=document_id,
                        number=str(c.get("number") or ""),
                        title=str(c.get("title") or ""),
                        text=str(c.get("text") or ""),
                        page=c.get("page"),
                        section=c.get("section"),
                    )
                )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("storing clauses", exc)

    @staticmethod
    @_retry_read
    async def list_by_tender(session: AsyncSession, tender_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                await session.execute(
                    select(ClauseRow, DocumentRow.filename)
                    .outerjoin(DocumentRow, ClauseRow.document_id == DocumentRow.id)
                    .where(ClauseRow.tender_id == tender_id)
                    .order_by(ClauseRow.created_at.asc())
                )
            ).all()
            out = []
            for clause, filename in rows:
                out.append(
                    {
                        "id": clause.id,
                        "number": clause.number,
                        "title": clause.title,
                        "text": clause.text,
                        "sourceDocumentId": clause.document_id or "",
                        "sourceDocumentName": filename or "",
                        "page": clause.page,
                        "section": clause.section,
                    }
                )
            return out
        except SQLAlchemyError as exc:
            raise _db_error("listing clauses", exc)

    @staticmethod
    @_retry_read
    async def find(
        session: AsyncSession, tender_id: str, clause_id: str
    ) -> Optional[dict[str, Any]]:
        try:
            row = (
                await session.execute(
                    select(ClauseRow, DocumentRow.filename)
                    .outerjoin(DocumentRow, ClauseRow.document_id == DocumentRow.id)
                    .where(ClauseRow.id == clause_id, ClauseRow.tender_id == tender_id)
                )
            ).first()
            if row is None:
                return None
            clause, filename = row
            return {
                "id": clause.id,
                "number": clause.number,
                "title": clause.title,
                "text": clause.text,
                "sourceDocumentId": clause.document_id or "",
                "sourceDocumentName": filename or "",
                "page": clause.page,
                "section": clause.section,
            }
        except SQLAlchemyError as exc:
            raise _db_error("reading clause", exc)

    @staticmethod
    async def delete_by_document(session: AsyncSession, document_id: str) -> None:
        try:
            await session.execute(delete(ClauseRow).where(ClauseRow.document_id == document_id))
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("deleting clauses", exc)

    @staticmethod
    async def delete_stale_for_document(session: AsyncSession, tender_id: str, document_id: str) -> None:
        """Drop opportunity snapshots computed from a doc set that just changed."""
        try:
            await session.execute(
                delete(AnalysisRow).where(
                    AnalysisRow.tender_id == tender_id,
                    AnalysisRow.kind == "opportunity",
                    (AnalysisRow.document_id == document_id) | (AnalysisRow.document_id.is_(None)),
                )
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("deleting stale analyses", exc)


class AnalysisRepository:
    @staticmethod
    def _to_record(row: AnalysisRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "tenderId": row.tender_id,
            "documentId": row.document_id,
            "kind": row.kind,
            "engine": row.engine,
            "result": dict(row.result),
            "createdAt": row.created_at.isoformat() if row.created_at else "",
        }

    @staticmethod
    async def save(
        session: AsyncSession,
        *,
        analysis_id: str,
        tender_id: str,
        document_id: str | None,
        kind: str,
        result: dict[str, Any],
        engine: str,
    ) -> dict[str, Any]:
        try:
            row = AnalysisRow(
                id=analysis_id,
                tender_id=tender_id,
                document_id=document_id,
                kind=kind,
                result=dict(result),
                engine=engine,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AnalysisRepository._to_record(row)
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _db_error("storing analysis", exc)

    @staticmethod
    @_retry_read
    async def latest(
        session: AsyncSession, tender_id: str, kind: str
    ) -> Optional[dict[str, Any]]:
        try:
            row = (
                await session.execute(
                    select(AnalysisRow)
                    .where(AnalysisRow.tender_id == tender_id, AnalysisRow.kind == kind)
                    .order_by(AnalysisRow.created_at.desc())
                )
            ).scalars().first()
            return AnalysisRepository._to_record(row) if row is not None else None
        except SQLAlchemyError as exc:
            raise _db_error("reading analysis", exc)
