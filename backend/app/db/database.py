"""Async SQLAlchemy engine + session factory for Neon PostgreSQL.

- Engine is created lazily so the app can import without a configured DB.
- DSN query params asyncpg cannot handle (e.g. ``sslmode``) are stripped and
  mapped to an explicit SSL context instead — Neon requires SSL.
- ``pool_pre_ping`` + ``pool_recycle`` tolerate Neon's idle-compute suspend.
- The raw DATABASE_URL is never logged.
"""
from __future__ import annotations

import logging
import ssl
from typing import AsyncIterator
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings
from ..core.errors import ApiError

log = logging.getLogger("stamas.db")

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_dsn(raw: str) -> tuple[str, dict]:
    """Return (asyncpg-safe DSN, connect_args) for a Neon-style URL."""
    url = raw.strip()
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+asyncpg://"):
        raise ApiError(
            "DATABASE_URL must use the postgresql+asyncpg:// scheme.", 500
        )
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = (query.pop("sslmode", "") or "require").lower()
    query.pop("ssl", None)
    query.pop("sslrootcert", None)
    query.pop("channel_binding", None)
    timeout = 10
    if "connect_timeout" in query:
        try:
            timeout = int(query.pop("connect_timeout"))
        except ValueError:
            pass
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(f"{k}={v}" for k, v in query.items()), ""))
    if sslmode == "disable":
        connect_args: dict = {"timeout": timeout}
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        connect_args = {"ssl": ctx, "timeout": timeout}
    return clean, connect_args


def get_engine():
    """Lazily create (and cache) the async engine. Raises 503 if unconfigured."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    if not settings.database_configured:
        raise ApiError(
            "Database is not configured. Set DATABASE_URL in backend/.env.", 503
        )
    dsn, connect_args = _normalize_dsn(settings.DATABASE_URL)
    try:
        _engine = create_async_engine(
            dsn,
            connect_args=connect_args,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    except ApiError:
        raise
    except Exception as exc:
        log.error("Failed to create database engine: %s", type(exc).__name__)
        raise ApiError("Database unavailable. Try again shortly.", 503)
    return _engine


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields one AsyncSession per request."""
    global _session_factory
    get_engine()  # raises 503 when unconfigured
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


class _SessionContext:
    """`async with session_scope() as session:` for non-route code (e.g. health)."""

    async def __aenter__(self) -> AsyncSession:
        global _session_factory
        get_engine()  # raises 503 when unconfigured
        assert _session_factory is not None
        self._session = _session_factory()
        return self._session

    async def __aexit__(self, *args) -> None:
        await self._session.close()


def session_scope() -> _SessionContext:
    return _SessionContext()


async def check_connection() -> bool:
    """SELECT 1 probe. Never raises, never logs credentials."""
    try:
        engine = get_engine()
    except ApiError:
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError) as exc:
        log.warning("Database health probe failed: %s", type(exc).__name__)
        return False
    except Exception as exc:
        log.warning("Database health probe failed: %s", type(exc).__name__)
        return False


async def dispose_engine() -> None:
    """Close pooled connections (app shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
