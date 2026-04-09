"""
engine.py — backward-compatible re-export shim.

All database access now goes through nexus.db.session.
This file re-exports the engine and session factory for any legacy code
that imports from nexus.db.engine.
"""

from __future__ import annotations

from nexus.db.session import (  # noqa: F401 — re-export for legacy imports
    async_session as async_session_factory,
    engine,
    get_session,
    session_ctx,
)

__all__ = ["engine", "async_session_factory", "get_session", "session_ctx"]
