"""
Database package — async SQLAlchemy + pgvector/AlloyDB ScaNN.

Public surface:
    engine        — AsyncEngine (shared singleton)
    async_session — async_sessionmaker
    get_session   — FastAPI dependency
    session_ctx   — async context manager for non-request code
    Base          — SQLAlchemy DeclarativeBase (all models inherit this)
"""

from nexus.db.session import (  # noqa: F401
    async_session,
    engine,
    get_session,
    session_ctx,
)
from nexus.db.models import Base  # noqa: F401

__all__ = [
    "engine",
    "async_session",
    "get_session",
    "session_ctx",
    "Base",
]
