"""Alembic environment — async engine, URL from settings (never logged)."""
from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

# backend/ on sys.path so `import app...` works when alembic runs from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _engine_config() -> dict:
    if not settings.database_configured:
        raise RuntimeError("DATABASE_URL is not set. Add it to backend/.env first.")
    from app.db.database import _normalize_dsn

    dsn, connect_args = _normalize_dsn(settings.DATABASE_URL)
    return {"sqlalchemy.url": dsn, "sqlalchemy.connect_args": connect_args}


def run_migrations_offline() -> None:
    dsn, _ = _engine_config()
    context.configure(
        url=dsn,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    cfg = _engine_config()
    connectable = async_engine_from_config(
        {"sqlalchemy.url": cfg["sqlalchemy.url"]},
        connect_args=cfg["sqlalchemy.connect_args"],
        prefix="sqlalchemy.",
        poolclass=None,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
