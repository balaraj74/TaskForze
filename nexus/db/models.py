"""SQLAlchemy ORM models — AlloyDB (PostgreSQL + pgvector/ScaNN) + SQLite dev fallback."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from nexus.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")


# ── Conditional type resolution ───────────────────────────────────────────────
if _is_sqlite:
    _UUID = String(36)
    _JSONB = JSON
    _ARRAY_Text = JSON   # JSON array fallback
    _Vector = lambda dim: Text  # noqa: E731 — store as JSON string in dev
else:
    from pgvector.sqlalchemy import Vector as _PgVector
    from sqlalchemy.dialects.postgresql import (
        ARRAY as _PgARRAY,
        JSONB as _PgJSONB,
        UUID as _PgUUID,
    )

    _UUID = _PgUUID(as_uuid=True)
    _JSONB = _PgJSONB
    _ARRAY_Text = _PgARRAY(Text)
    _Vector = lambda dim: _PgVector(dim)  # noqa: E731


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str | uuid.UUID:
    return str(uuid.uuid4()) if _is_sqlite else uuid.uuid4()


class Base(DeclarativeBase):
    """Shared declarative base — all models must inherit from this."""


# ── Tasks ─────────────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_task_priority"),
        CheckConstraint(
            "status IN ('pending','in_progress','done','blocked')",
            name="ck_task_status",
        ),
    )

    id                   = Column(_UUID, primary_key=True, default=_new_uuid)
    title                = Column(Text, nullable=False)
    description          = Column(Text, default="")
    priority             = Column(Integer, default=3, nullable=False)
    deadline             = Column(DateTime(timezone=True), nullable=True)
    effort_hours         = Column(Float, default=1.0)
    status               = Column(String(20), default="pending", nullable=False)
    cognitive_load_score = Column(Float, default=0.0)
    linked_workflow_id   = Column(_UUID, nullable=True)
    tags                 = Column(_ARRAY_Text if not _is_sqlite else JSON, default=list)
    created_at           = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at           = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    reminders = relationship("ReminderLog", back_populates="task", lazy="selectin", cascade="all, delete-orphan")
    notes     = relationship("Note",        back_populates="task", lazy="selectin")


# ── Task Dependencies ─────────────────────────────────────────────────────────
class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint("task_id != depends_on", name="ck_no_self_dep"),
    )

    task_id    = Column(_UUID, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on = Column(_UUID, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)


# ── Notes ─────────────────────────────────────────────────────────────────────
class Note(Base):
    __tablename__ = "notes"

    id              = Column(_UUID, primary_key=True, default=_new_uuid)
    title           = Column(Text, default="")
    content         = Column(Text, nullable=False)
    tags            = Column(_ARRAY_Text if not _is_sqlite else JSON, default=list)
    embedding       = Column(_Vector(768), nullable=True)
    linked_task_id  = Column(_UUID, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    linked_event_id = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at      = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    task = relationship("Task", back_populates="notes")


# ── Workflow Runs ─────────────────────────────────────────────────────────────
class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed')",
            name="ck_workflow_status",
        ),
    )

    id            = Column(_UUID, primary_key=True, default=_new_uuid)
    user_intent   = Column(Text, default="")
    plan          = Column(_JSONB if not _is_sqlite else JSON, default=list)
    context       = Column(_JSONB if not _is_sqlite else JSON, default=dict)
    agent_outputs = Column(_JSONB if not _is_sqlite else JSON, default=dict)
    trace         = Column(_JSONB if not _is_sqlite else JSON, default=list)
    status        = Column(String(20), default="running")
    duration_ms   = Column(Integer, nullable=True)
    created_at    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at  = Column(DateTime(timezone=True), nullable=True)


# ── Active Workflows ──────────────────────────────────────────────────────────
class ActiveWorkflow(Base):
    __tablename__ = "active_workflows"

    user_id     = Column(Text, primary_key=True)
    workflow_id = Column(_UUID, ForeignKey("workflow_runs.id"), nullable=True)
    intent      = Column(Text, nullable=True)
    started_at  = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ── Reminder Log ──────────────────────────────────────────────────────────────
class ReminderLog(Base):
    __tablename__ = "reminder_log"
    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp','voice')", name="ck_reminder_channel"),
        CheckConstraint(
            "outcome IN ('ack','snoozed','escalated','no_response') OR outcome IS NULL",
            name="ck_reminder_outcome",
        ),
    )

    id              = Column(_UUID, primary_key=True, default=_new_uuid)
    task_id         = Column(_UUID, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    channel         = Column(String(20), nullable=False)
    sent_at         = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    outcome         = Column(String(20), nullable=True)
    snooze_until    = Column(DateTime(timezone=True), nullable=True)
    delivery_ms     = Column(Integer, nullable=True)

    task = relationship("Task", back_populates="reminders")


# ── User Preferences ──────────────────────────────────────────────────────────
class UserPreference(Base):
    __tablename__ = "user_preferences"

    key        = Column(Text, primary_key=True)
    value      = Column(_JSONB if not _is_sqlite else JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


# ── AutoForze Habit Rules ─────────────────────────────────────────────────────
SIGNAL_TYPES = (
    "time_pattern", "instant_ack", "overload_detected", "channel_preference",
    "day_of_week_pattern", "snooze_loop", "deadline_proximity", "novel_context",
)


class AutoForzeHabitRule(Base):
    __tablename__ = "autoforze_habit_rules"
    __table_args__ = (
        CheckConstraint(
            f"signal_type IN ({', '.join(repr(s) for s in SIGNAL_TYPES)})",
            name="ck_habit_signal_type",
        ),
        CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name="ck_habit_confidence"),
    )

    id               = Column(Text, primary_key=True)
    name             = Column(Text, nullable=False)
    signal_type      = Column(Text, nullable=True)
    description      = Column(Text, nullable=True)
    condition_data   = Column(_JSONB if not _is_sqlite else JSON, default=dict)
    action_data      = Column(_JSONB if not _is_sqlite else JSON, default=dict)
    confidence       = Column(Float, default=0.5)
    times_applied    = Column(Integer, default=0)
    times_successful = Column(Integer, default=0)
    # is_trusted is a generated column in AlloyDB; mirror as property in Python
    created_at       = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at       = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    @property
    def is_trusted(self) -> bool:
        return self.confidence >= 0.7 and self.times_applied >= 3


# ── AutoForze Solidified Behaviors ────────────────────────────────────────────
class AutoForzeBehavior(Base):
    __tablename__ = "autoforze_behaviors"

    id               = Column(Text, primary_key=True)
    rule_id          = Column(Text, ForeignKey("autoforze_habit_rules.id", ondelete="SET NULL"), nullable=True)
    task_id          = Column(_UUID, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    context_snapshot = Column(_JSONB if not _is_sqlite else JSON, default=dict)
    outcome          = Column(Text, nullable=True)
    solidified_at    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ── AutoForze Heartbeat Metrics ───────────────────────────────────────────────
class AutoForzeHeartbeat(Base):
    __tablename__ = "autoforze_heartbeat"

    id             = Column(_UUID, primary_key=True, default=_new_uuid)
    rules_active   = Column(Integer, default=0)
    reminders_sent = Column(Integer, default=0)
    loop_ms        = Column(Integer, default=0)
    recorded_at    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
