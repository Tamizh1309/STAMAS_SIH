"""Add analyses table for persisted AI decision-support results.

Revision ID: 0002_analyses
Revises: 0001_initial
Create Date: 2026-09-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_analyses"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tender_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="opportunity"),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=False, server_default="Local Rule Engine"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyses_tender_id", "analyses", ["tender_id"], unique=False)
    op.create_index("ix_analyses_document_id", "analyses", ["document_id"], unique=False)
    op.create_index("ix_analyses_kind", "analyses", ["kind"], unique=False)
    op.create_index("ix_analyses_tender_kind_created", "analyses", ["tender_id", "kind", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("analyses")
