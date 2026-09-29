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
from .seed_data import MOCK_TENDERS

log = logging.getLogger("stamas.db.repo")

_in_memory_tenders: list[dict[str, Any]] = [dict(t) for t in MOCK_TENDERS]


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
    async def seed_initial_tenders(session: AsyncSession | None) -> None:
        """Seed canonical mock tenders (e.g. tender-1 CPCL/REF/2026/094) into PostgreSQL if not present."""
        if session is None:
            return
        from .seed_data import MOCK_TENDERS
        try:
            for mock in MOCK_TENDERS:
                existing = await session.get(TenderRow, mock["id"])
                if existing is None:
                    by_no = (
                        await session.execute(
                            select(TenderRow).where(TenderRow.tender_no == mock["tenderNo"])
                        )
                    ).scalars().first()
                    if by_no is not None:
                        if by_no.id != mock["id"]:
                            await session.delete(by_no)
                            await session.flush()
                            session.add(
                                TenderRow(
                                    id=mock["id"],
                                    tender_no=mock["tenderNo"],
                                    data=dict(mock),
                                )
                            )
                        else:
                            by_no.data = dict(mock)
                    else:
                        session.add(
                            TenderRow(
                                id=mock["id"],
                                tender_no=mock["tenderNo"],
                                data=dict(mock),
                            )
                        )
            await session.commit()
        except Exception as exc:
            log.warning("Initial tender seeding skipped: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass

    @staticmethod
    async def list_all(session: AsyncSession | None) -> list[dict[str, Any]]:
        if session is not None:
            try:
                rows = (
                    await session.execute(
                        select(TenderRow).order_by(TenderRow.created_at.desc())
                    )
                ).scalars().all()
                if not rows or not any(r.tender_no == "CPCL/REF/2026/094" for r in rows):
                    await TenderRepository.seed_initial_tenders(session)
                    rows = (
                        await session.execute(
                            select(TenderRow).order_by(TenderRow.created_at.desc())
                        )
                    ).scalars().all()
                return [dict(r.data) for r in rows]
            except Exception as exc:
                log.error("Database list_all failed: %s", exc)
                raise ApiError("Failed to fetch tenders from database.", 500)
        return []

    @staticmethod
    async def get_by_id(session: AsyncSession | None, tender_id: str) -> Optional[dict[str, Any]]:
        if session is not None:
            try:
                row = await session.get(TenderRow, tender_id)
                if row is None and tender_id in ("tender-1", "tender-2", "tender-3"):
                    await TenderRepository.seed_initial_tenders(session)
                    row = await session.get(TenderRow, tender_id)
                if row is not None:
                    return dict(row.data)
                return None
            except Exception as exc:
                log.error("Database get_by_id failed: %s", exc)
                raise ApiError("Failed to fetch tender from database.", 500)
        return None

    @staticmethod
    async def get_by_tender_no(session: AsyncSession | None, tender_no: str) -> Optional[dict[str, Any]]:
        if session is not None:
            try:
                row = (
                    await session.execute(
                        select(TenderRow).where(TenderRow.tender_no == tender_no)
                    )
                ).scalars().first()
                if row is None and tender_no == "CPCL/REF/2026/094":
                    await TenderRepository.seed_initial_tenders(session)
                    row = (
                        await session.execute(
                            select(TenderRow).where(TenderRow.tender_no == tender_no)
                        )
                    ).scalars().first()
                if row is not None:
                    return dict(row.data)
                return None
            except Exception as exc:
                log.error("Database get_by_tender_no failed: %s", exc)
                raise ApiError("Failed to fetch tender from database.", 500)
        return None

    @staticmethod
    async def create(
        session: AsyncSession | None,
        tender_id: str,
        tender_no: str,
        data: dict[str, Any],
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        if session is not None:
            try:
                row = TenderRow(
                    id=tender_id,
                    tender_no=tender_no,
                    data=dict(data),
                    created_at=created_at or _utcnow(),
                )
                session.add(row)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise ApiError(
                    f"A tender with number \"{tender_no}\" already exists.", 409
                )
            except Exception as exc:
                log.error("Database create tender failed: %s", exc)
                await session.rollback()
                raise ApiError("Failed to save tender to database.", 500)
        return dict(data)

    @staticmethod
    async def save(session: AsyncSession | None, tender_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Replace the whole tender document (bidders + stats live inside)."""
        if session is not None:
            try:
                row = await session.get(TenderRow, tender_id)
                if row is not None:
                    row.data = dict(data)
                    await session.commit()
            except Exception as exc:
                log.error("Database save tender failed: %s", exc)
                await session.rollback()
                raise ApiError("Failed to update tender in database.", 500)
        return dict(data)

    @staticmethod
    async def count(session: AsyncSession | None) -> int:
        if session is not None:
            try:
                return (
                    await session.execute(select(func.count()).select_from(TenderRow))
                ).scalar_one()
            except Exception as exc:
                log.warning("Database count failed: %s", exc)
                return 0
        return 0



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
    async def list_by_tender(session: AsyncSession | None, tender_id: str) -> list[dict[str, Any]]:
        if session is None:
            return []
        try:
            rows = (
                await session.execute(
                    select(DocumentRow)
                    .where(DocumentRow.tender_id == tender_id)
                    .order_by(DocumentRow.uploaded_at.asc())
                )
            ).scalars().all()
            return [DocumentRepository._to_meta(r) for r in rows]
        except Exception as exc:
            log.warning("Database list_by_tender failed: %s", exc)
            return []

    @staticmethod
    async def get(session: AsyncSession | None, tender_id: str, document_id: str) -> Optional[dict[str, Any]]:
        if session is None:
            return None
        try:
            row = await session.get(DocumentRow, document_id)
            if row is None or row.tender_id != tender_id:
                return None
            return DocumentRepository._to_meta(row)
        except Exception as exc:
            log.warning("Database get document failed: %s", exc)
            return None

    @staticmethod
    async def create(
        session: AsyncSession | None,
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
        meta = {
            "id": document_id,
            "tenderId": tender_id,
            "fileName": filename,
            "fileType": file_type,
            "mimeType": mime_type,
            "size": file_size,
            "status": status,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "extractedTextLength": 0,
            "pageCount": None,
            "error": None,
        }
        if session is None:
            return meta
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
        except Exception as exc:
            log.warning("Database create document failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass
            return meta

    @staticmethod
    async def update(session: AsyncSession | None, document_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        if session is None:
            return None
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
        except Exception as exc:
            log.warning("Database update document failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    async def delete(session: AsyncSession | None, tender_id: str, document_id: str) -> Optional[dict[str, Any]]:
        if session is None:
            return None
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
        except Exception as exc:
            log.warning("Database delete document failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    async def get_text(
        session: AsyncSession | None, tender_id: str, document_id: str, max_chars: int = 20000
    ) -> Optional[tuple[dict[str, Any], str, bool]]:
        if session is None:
            return None
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
        except Exception as exc:
            log.warning("Database get_text failed: %s", exc)
            return None


class ClauseRepository:
    @staticmethod
    async def create_many(
        session: AsyncSession | None, tender_id: str, document_id: str, clauses: list[dict[str, Any]]
    ) -> None:
        if session is None:
            return
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
        except Exception as exc:
            log.warning("Database create_many clauses failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass

    @staticmethod
    async def list_by_tender(session: AsyncSession | None, tender_id: str) -> list[dict[str, Any]]:
        if session is None:
            return []
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
        except Exception as exc:
            log.warning("Database list_by_tender clauses failed: %s", exc)
            return []

    @staticmethod
    async def find(
        session: AsyncSession | None, tender_id: str, clause_id: str
    ) -> Optional[dict[str, Any]]:
        if session is None:
            return None
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
        except Exception as exc:
            log.warning("Database find clause failed: %s", exc)
            return None

    @staticmethod
    async def delete_by_document(session: AsyncSession | None, document_id: str) -> None:
        if session is None:
            return
        try:
            await session.execute(delete(ClauseRow).where(ClauseRow.document_id == document_id))
            await session.commit()
        except Exception as exc:
            log.warning("Database delete clauses failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass

    @staticmethod
    async def delete_stale_for_document(session: AsyncSession | None, tender_id: str, document_id: str) -> None:
        if session is None:
            return
        try:
            await session.execute(
                delete(AnalysisRow).where(
                    AnalysisRow.tender_id == tender_id,
                    AnalysisRow.kind == "opportunity",
                    (AnalysisRow.document_id == document_id) | (AnalysisRow.document_id.is_(None)),
                )
            )
            await session.commit()
        except Exception as exc:
            log.warning("Database delete_stale_for_document failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass


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
        session: AsyncSession | None,
        *,
        analysis_id: str,
        tender_id: str,
        document_id: str | None,
        kind: str,
        result: dict[str, Any],
        engine: str,
    ) -> dict[str, Any]:
        record = {
            "id": analysis_id,
            "tenderId": tender_id,
            "documentId": document_id,
            "kind": kind,
            "engine": engine,
            "result": dict(result),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        if session is None:
            return record
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
        except Exception as exc:
            log.warning("Database save analysis failed: %s", exc)
            try:
                await session.rollback()
            except Exception:
                pass
            return record

    @staticmethod
    async def latest(
        session: AsyncSession | None, tender_id: str, kind: str
    ) -> Optional[dict[str, Any]]:
        if session is None:
            return None
        try:
            row = (
                await session.execute(
                    select(AnalysisRow)
                    .where(AnalysisRow.tender_id == tender_id, AnalysisRow.kind == kind)
                    .order_by(AnalysisRow.created_at.desc())
                )
            ).scalars().first()
            return AnalysisRepository._to_record(row) if row is not None else None
        except Exception as exc:
            log.warning("Database latest analysis failed: %s", exc)
            return None

