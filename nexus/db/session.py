# ──────────────────────────────────────────────────────────────────────────
# AlloyDB Session Layer  —  nexus/db/session.py
# Production-grade async engine with AlloyDB Auth Proxy support.
# Connects via localhost:5432 when the Auth Proxy sidecar is running.
# Falls back transparently to SQLite when DATABASE_URL starts with "sqlite".
# ──────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nexus.config import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {"echo": False}

if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "server_settings": {"application_name": "taskforze"},
            "command_timeout": 30,
        },
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autobegin=True,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:  # type: ignore[misc]
    """FastAPI dependency — yields a managed async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager form — use in non-FastAPI code (agents, tools)."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
