"""SQLAlchemy 2.x ORM models for Neon PostgreSQL.

Nested tender content (bidders, evaluated clauses, summary stats) lives in a
JSONB ``data`` column so the API dict shapes stay byte-identical to the
previous in-memory store. Documents keep metadata + extracted text in the
database; the uploaded bytes stay on disk under backend/storage/documents/.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TenderRow(Base):
    __tablename__ = "tenders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tender_no: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["DocumentRow"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True
    )
    clauses: Mapped[list["ClauseRow"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentRow(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Server-side path only — never serialized to the frontend.
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="UPLOADED", index=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extracted_text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tender: Mapped["TenderRow"] = relationship(back_populates="documents")
    clauses: Mapped[list["ClauseRow"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class ClauseRow(Base):
    __tablename__ = "clauses"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    number: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tender: Mapped["TenderRow"] = relationship(back_populates="clauses")
    document: Mapped["DocumentRow | None"] = relationship(back_populates="clauses")


Index("ix_documents_tender_status", DocumentRow.tender_id, DocumentRow.status)
Index("ix_clauses_tender_created", ClauseRow.tender_id, ClauseRow.created_at)


class AnalysisRow(Base):
    """Persisted AI analysis (e.g. tender opportunity) — decision support, not verdicts."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tender_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="opportunity", index=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    engine: Mapped[str] = mapped_column(String(64), nullable=False, default="Local Rule Engine")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tender: Mapped["TenderRow"] = relationship()
    document: Mapped["DocumentRow | None"] = relationship()
