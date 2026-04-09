"""
Database tool functions — AlloyDB-backed CRUD + semantic search for
tasks, notes, workflows, reminders, and AutoForze rules.

All public functions open their own async session via session_ctx() so
callers never need to manage sessions directly.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, select, text, update

from nexus.config import settings
from nexus.db.session import session_ctx
from nexus.db.models import (
    ActiveWorkflow,
    AutoForzeBehavior,
    AutoForzeHabitRule,
    AutoForzeHeartbeat,
    Note,
    ReminderLog,
    Task,
    TaskDependency,
    UserPreference,
    WorkflowRun,
)
from nexus.tools.dependency_graph import TaskDependencyGraph

_is_sqlite = settings.database_url.startswith("sqlite")


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_uuid(value: str | uuid.UUID) -> str | uuid.UUID:
    """Return str for SQLite, UUID object for PostgreSQL."""
    if _is_sqlite:
        return str(value)
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _new_id() -> str | uuid.UUID:
    return str(uuid.uuid4()) if _is_sqlite else uuid.uuid4()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id":                   str(task.id),
        "title":                task.title,
        "description":          task.description or "",
        "priority":             task.priority,
        "deadline":             task.deadline.isoformat() if task.deadline else None,
        "effort_hours":         task.effort_hours,
        "status":               task.status,
        "cognitive_load_score": task.cognitive_load_score,
        "linked_workflow_id":   str(task.linked_workflow_id) if task.linked_workflow_id else None,
        "tags":                 task.tags or [],
        "created_at":           task.created_at.isoformat() if task.created_at else None,
        "updated_at":           task.updated_at.isoformat() if task.updated_at else None,
    }


def _serialize_note(note: Note) -> dict[str, Any]:
    return {
        "id":              str(note.id),
        "title":           note.title or "",
        "content":         note.content,
        "tags":            note.tags or [],
        "linked_task_id":  str(note.linked_task_id) if note.linked_task_id else None,
        "linked_event_id": note.linked_event_id,
        "created_at":      note.created_at.isoformat() if note.created_at else None,
    }


def _serialize_workflow(workflow: WorkflowRun) -> dict[str, Any]:
    return {
        "id":            str(workflow.id),
        "user_intent":   workflow.user_intent,
        "plan":          workflow.plan or [],
        "context":       workflow.context or {},
        "agent_outputs": workflow.agent_outputs or {},
        "trace":         workflow.trace or [],
        "status":        workflow.status,
        "duration_ms":   workflow.duration_ms,
        "created_at":    workflow.created_at.isoformat() if workflow.created_at else None,
        "completed_at":  workflow.completed_at.isoformat() if workflow.completed_at else None,
    }


# ─── Tasks ────────────────────────────────────────────────────────────────────

async def create_task(data: dict[str, Any]) -> dict[str, Any]:
    """Create a task and optionally register dependency edges."""
    async with session_ctx() as session:
        task = Task(
            id=_new_id(),
            title=data["title"],
            description=data.get("description", ""),
            priority=int(data.get("priority", 3) or 3),
            deadline=_parse_datetime(data.get("deadline")),
            effort_hours=float(data.get("effort_hours") or 1.0),
            status=data.get("status", "pending"),
            cognitive_load_score=data.get("cognitive_load_score", 0.0),
            tags=data.get("tags") or [],
            linked_workflow_id=_normalize_uuid(data["linked_workflow_id"])
            if data.get("linked_workflow_id") else None,
        )
        session.add(task)
        await session.flush()
        task_id = str(task.id)

    for dep_id in (data.get("dependencies") or []):
        await add_dependency(task_id, str(dep_id))

    return await get_task_by_id(task_id) or {"id": task_id, "error": "created but not found"}


async def update_task(task_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update fields on an existing task."""
    payload = {k: v for k, v in updates.items() if v is not None}
    if "deadline" in payload:
        payload["deadline"] = _parse_datetime(payload["deadline"])
    if "linked_workflow_id" in payload and payload["linked_workflow_id"]:
        payload["linked_workflow_id"] = _normalize_uuid(payload["linked_workflow_id"])

    async with session_ctx() as session:
        await session.execute(
            update(Task)
            .where(Task.id == _normalize_uuid(task_id))
            .values(**payload, updated_at=_utcnow())
        )

    result = await get_task_by_id(task_id)
    return result or {"error": f"Task {task_id} not found"}


async def get_tasks(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve tasks ordered by creation date, with optional status filter."""
    async with session_ctx() as session:
        stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Task.status == status)
        result = await session.execute(stmt)
        return [_serialize_task(t) for t in result.scalars().all()]


async def get_task_by_id(task_id: str) -> dict[str, Any] | None:
    async with session_ctx() as session:
        result = await session.execute(
            select(Task).where(Task.id == _normalize_uuid(task_id))
        )
        task = result.scalar_one_or_none()
        return _serialize_task(task) if task else None


async def get_upcoming_tasks(window_minutes: int = 130) -> list[dict[str, Any]]:
    """Get incomplete tasks due within window, including slightly overdue ones."""
    if not _is_sqlite:
        # Use the AlloyDB stored function for efficiency
        async with session_ctx() as session:
            result = await session.execute(
                text("SELECT * FROM get_upcoming_tasks(:w)"),
                {"w": window_minutes},
            )
            rows = result.mappings().all()
            return [
                {
                    "id":                   str(row["id"]),
                    "title":                row["title"],
                    "deadline":             row["deadline"].isoformat() if row["deadline"] else None,
                    "priority":             row["priority"],
                    "status":               row["status"],
                    "effort_hours":         row["effort_hours"],
                    "minutes_left":         round(float(row["minutes_left"] or 0), 1),
                    "priority_score":       float(row["priority_score"] or 0),
                    "last_reminder_sent":   row["last_reminder_sent"].isoformat() if row["last_reminder_sent"] else None,
                    "acknowledged_at":      row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None,
                    "snooze_until":         row["snooze_until"].isoformat() if row["snooze_until"] else None,
                    "last_outcome":         row["last_outcome"],
                }
                for row in rows
            ]

    # SQLite fallback
    async with session_ctx() as session:
        now = _utcnow()
        cutoff = now + timedelta(minutes=window_minutes)
        stmt = (
            select(Task)
            .where(
                and_(
                    Task.deadline.is_not(None),
                    Task.deadline <= cutoff,
                    Task.deadline >= now - timedelta(minutes=10),
                    Task.status.in_(["pending", "in_progress"]),
                )
            )
            .order_by(Task.deadline.asc())
        )
        result = await session.execute(stmt)
        return [_serialize_task(t) for t in result.scalars().all()]


async def compute_daily_load(date_str: str, meeting_hours: float = 0.0) -> dict[str, Any]:
    """Compute the cognitive load for a given UTC day."""
    if not _is_sqlite:
        async with session_ctx() as session:
            result = await session.execute(
                text("SELECT compute_daily_load(CAST(:d AS DATE))"),
                {"d": date_str},
            )
            db_load = float(result.scalar() or 0)
        load_score = round(db_load + (meeting_hours * 1.5), 2)
        return {
            "date":          date_str,
            "meeting_hours": meeting_hours,
            "load_score":    load_score,
            "is_heavy":      load_score > 8,
        }

    # SQLite fallback
    target_start = _parse_datetime(f"{date_str}T00:00:00+00:00")
    if target_start is None:
        from datetime import time
        target_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    target_end = target_start + timedelta(days=1)

    async with session_ctx() as session:
        stmt = select(Task).where(
            and_(
                Task.deadline.is_not(None),
                Task.deadline >= target_start,
                Task.deadline < target_end,
                Task.status.in_(["pending", "in_progress"]),
            )
        )
        result = await session.execute(stmt)
        tasks = result.scalars().all()

    task_count = len(tasks)
    avg_load = sum(t.cognitive_load_score or t.priority for t in tasks) / max(task_count, 1)
    load_score = round((meeting_hours * 1.5) + (task_count * 0.5) + avg_load, 2)
    return {
        "date":          date_str,
        "meeting_hours": meeting_hours,
        "task_count":    task_count,
        "load_score":    load_score,
        "is_heavy":      load_score > 8,
    }


# ─── Dependencies ─────────────────────────────────────────────────────────────

async def get_all_dependencies() -> list[dict[str, str]]:
    async with session_ctx() as session:
        result = await session.execute(select(TaskDependency))
        return [
            {"task_id": str(d.task_id), "depends_on": str(d.depends_on)}
            for d in result.scalars().all()
        ]


async def add_dependency(task_id: str, depends_on_id: str) -> dict[str, str]:
    """Add a DAG edge, validating acyclicity first."""
    tasks = await get_tasks(limit=500)
    dependencies = await get_all_dependencies()

    if any(d["task_id"] == task_id and d["depends_on"] == depends_on_id for d in dependencies):
        return {"task_id": task_id, "depends_on": depends_on_id}  # already exists

    graph = TaskDependencyGraph()
    graph.load_from_db(tasks, dependencies)
    graph.add_dependency(task_id, depends_on_id)  # raises if cyclic

    async with session_ctx() as session:
        session.add(
            TaskDependency(
                task_id=_normalize_uuid(task_id),
                depends_on=_normalize_uuid(depends_on_id),
            )
        )

    return {"task_id": task_id, "depends_on": depends_on_id}


async def get_dependency_graph(task_id: str | None = None) -> list[dict[str, str]]:
    async with session_ctx() as session:
        stmt = select(TaskDependency)
        if task_id:
            stmt = stmt.where(TaskDependency.task_id == _normalize_uuid(task_id))
        result = await session.execute(stmt)
        return [
            {"task_id": str(d.task_id), "depends_on": str(d.depends_on)}
            for d in result.scalars().all()
        ]


async def get_actionable_tasks(limit: int = 20) -> list[dict[str, Any]]:
    """Tasks with all dependencies satisfied (ready to start)."""
    tasks = await get_tasks(limit=500)
    dependencies = await get_all_dependencies()
    graph = TaskDependencyGraph()
    graph.load_from_db(tasks, dependencies)
    return graph.get_actionable_tasks()[:limit]


async def get_ranked_tasks(limit: int = 20) -> list[dict[str, Any]]:
    """All tasks ordered by priority × urgency × effort."""
    tasks = await get_tasks(limit=500)
    dependencies = await get_all_dependencies()
    graph = TaskDependencyGraph()
    graph.load_from_db(tasks, dependencies)
    return graph.get_ranked_tasks()[:limit]


# ─── Notes ────────────────────────────────────────────────────────────────────

async def create_note(data: dict[str, Any]) -> dict[str, Any]:
    async with session_ctx() as session:
        note = Note(
            id=_new_id(),
            title=data.get("title", ""),
            content=data["content"],
            tags=data.get("tags") or [],
            linked_task_id=_normalize_uuid(data["linked_task_id"]) if data.get("linked_task_id") else None,
            linked_event_id=data.get("linked_event_id"),
        )
        session.add(note)
        await session.flush()
        return _serialize_note(note)


async def update_note(note_id: str, content: str) -> dict[str, Any]:
    async with session_ctx() as session:
        await session.execute(
            update(Note)
            .where(Note.id == _normalize_uuid(note_id))
            .values(content=content, updated_at=_utcnow())
        )
    return {"id": note_id, "updated": True}


async def get_note(note_id: str) -> dict[str, Any] | None:
    async with session_ctx() as session:
        result = await session.execute(
            select(Note).where(Note.id == _normalize_uuid(note_id))
        )
        note = result.scalar_one_or_none()
        return _serialize_note(note) if note else None


async def set_note_embedding(note_id: str, embedding: list[float]) -> None:
    """Store a vector embedding on a note."""
    if _is_sqlite:
        async with session_ctx() as session:
            await session.execute(
                update(Note)
                .where(Note.id == _normalize_uuid(note_id))
                .values(embedding=json.dumps(embedding))
            )
        return

    embedding_str = f"[{','.join(str(v) for v in embedding)}]"
    async with session_ctx() as session:
        await session.execute(
            text("UPDATE notes SET embedding = CAST(:emb AS vector) WHERE id = :nid"),
            {"emb": embedding_str, "nid": _normalize_uuid(note_id)},
        )


async def semantic_search(query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Vector similarity search using AlloyDB ScaNN (or recency fallback on sqlite)."""
    if _is_sqlite:
        async with session_ctx() as session:
            result = await session.execute(
                select(Note).order_by(Note.created_at.desc()).limit(top_k)
            )
            return [
                {**_serialize_note(n), "similarity": 0.0}
                for n in result.scalars().all()
            ]

    if not _is_sqlite:
        async with session_ctx() as session:
            result = await session.execute(
                text("SELECT * FROM semantic_search(CAST(:emb AS vector), :k)"),
                {"emb": f"[{','.join(str(v) for v in query_embedding)}]", "k": top_k},
            )
            rows = result.mappings().all()
            return [
                {
                    "id":             str(row["id"]),
                    "title":          row["title"],
                    "content":        row["content"],
                    "tags":           row["tags"] or [],
                    "linked_task_id": str(row["linked_task_id"]) if row["linked_task_id"] else None,
                    "similarity":     round(float(row["score"]), 4),
                }
                for row in rows
            ]

    return []


# ─── Workflows ────────────────────────────────────────────────────────────────

async def create_workflow(
    intent: str,
    plan: list[dict[str, Any]],
    workflow_id: str | None = None,
    context: dict[str, Any] | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    async with session_ctx() as session:
        workflow = WorkflowRun(
            id=_normalize_uuid(workflow_id or str(uuid.uuid4())),
            user_intent=intent,
            plan=plan,
            context=context or {},
            agent_outputs={},
            trace=trace or [],
            status="running",
        )
        session.add(workflow)
        await session.flush()
        return _serialize_workflow(workflow)


async def update_workflow(
    workflow_id: str,
    agent_outputs: dict[str, Any] | None = None,
    status: str | None = None,
    context: dict[str, Any] | None = None,
    trace: list[dict[str, Any]] | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if agent_outputs is not None:
        values["agent_outputs"] = agent_outputs
    if context is not None:
        values["context"] = context
    if trace is not None:
        values["trace"] = trace
    if duration_ms is not None:
        values["duration_ms"] = duration_ms
    if status is not None:
        values["status"] = status
        if status in ("completed", "failed"):
            values["completed_at"] = _utcnow()

    async with session_ctx() as session:
        await session.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == _normalize_uuid(workflow_id))
            .values(**values)
        )

    async with session_ctx() as session:
        result = await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == _normalize_uuid(workflow_id))
        )
        workflow = result.scalar_one_or_none()
        return _serialize_workflow(workflow) if workflow else {"id": workflow_id, "error": "not found"}


async def get_workflow(workflow_id: str) -> dict[str, Any] | None:
    async with session_ctx() as session:
        result = await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == _normalize_uuid(workflow_id))
        )
        workflow = result.scalar_one_or_none()
        return _serialize_workflow(workflow) if workflow else None


async def set_active_workflow(user_id: str, workflow_id: str, intent: str = "") -> None:
    """Register or replace the active workflow for a user (upsert)."""
    async with session_ctx() as session:
        existing = await session.get(ActiveWorkflow, user_id)
        if existing:
            existing.workflow_id = _normalize_uuid(workflow_id)
            existing.intent = intent
            existing.started_at = _utcnow()
        else:
            session.add(
                ActiveWorkflow(
                    user_id=user_id,
                    workflow_id=_normalize_uuid(workflow_id),
                    intent=intent,
                )
            )


async def get_active_workflow(user_id: str) -> dict[str, Any] | None:
    async with session_ctx() as session:
        result = await session.execute(
            select(ActiveWorkflow).where(ActiveWorkflow.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "user_id":     row.user_id,
            "workflow_id": str(row.workflow_id) if row.workflow_id else None,
            "intent":      row.intent,
            "started_at":  row.started_at.isoformat() if row.started_at else None,
        }


async def clear_active_workflow(user_id: str) -> None:
    async with session_ctx() as session:
        await session.execute(
            delete(ActiveWorkflow).where(ActiveWorkflow.user_id == user_id)
        )


# ─── Reminders ────────────────────────────────────────────────────────────────

async def log_reminder(
    task_id: str,
    channel: str,
    delivery_ms: int | None = None,
) -> dict[str, Any]:
    async with session_ctx() as session:
        log = ReminderLog(
            id=_new_id(),
            task_id=_normalize_uuid(task_id),
            channel=channel,
            delivery_ms=delivery_ms,
        )
        session.add(log)
        await session.flush()
        return {
            "id":       str(log.id),
            "task_id":  task_id,
            "channel":  channel,
            "sent_at":  log.sent_at.isoformat(),
        }


async def acknowledge_reminder(task_id: str, snooze_minutes: int | None = None) -> dict[str, Any]:
    """Mark the latest reminder as ACKed or snoozed."""
    now = _utcnow()
    snooze_until = (now + timedelta(minutes=snooze_minutes)) if snooze_minutes else None
    outcome = "snoozed" if snooze_minutes else "ack"

    async with session_ctx() as session:
        # Get the most recent un-ACKed reminder for this task
        result = await session.execute(
            select(ReminderLog)
            .where(
                and_(
                    ReminderLog.task_id == _normalize_uuid(task_id),
                    ReminderLog.acknowledged_at.is_(None),
                )
            )
            .order_by(ReminderLog.sent_at.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()
        if log:
            log.acknowledged_at = now
            log.outcome = outcome
            log.snooze_until = snooze_until

    # Mark task done if fully ACKed (no snooze)
    if not snooze_minutes:
        await update_task(task_id, {"status": "done"})

    return {"task_id": task_id, "outcome": outcome, "snooze_until": snooze_until.isoformat() if snooze_until else None}


async def get_reminder_history(task_id: str, limit: int = 10) -> list[dict[str, Any]]:
    async with session_ctx() as session:
        result = await session.execute(
            select(ReminderLog)
            .where(ReminderLog.task_id == _normalize_uuid(task_id))
            .order_by(ReminderLog.sent_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [
            {
                "id":              str(log.id),
                "channel":         log.channel,
                "sent_at":         log.sent_at.isoformat() if log.sent_at else None,
                "acknowledged_at": log.acknowledged_at.isoformat() if log.acknowledged_at else None,
                "outcome":         log.outcome,
                "snooze_until":    log.snooze_until.isoformat() if log.snooze_until else None,
            }
            for log in logs
        ]


# ─── User Preferences ─────────────────────────────────────────────────────────

async def get_preference(key: str) -> Any:
    async with session_ctx() as session:
        result = await session.execute(
            select(UserPreference).where(UserPreference.key == key)
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            return None
        val = pref.value
        # JSONB stores primitives as JSON-encoded; unwrap if needed
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        return val


async def set_preference(key: str, value: Any) -> None:
    async with session_ctx() as session:
        existing = await session.get(UserPreference, key)
        if existing:
            existing.value = value
            existing.updated_at = _utcnow()
        else:
            session.add(UserPreference(key=key, value=value))


async def get_all_preferences() -> dict[str, Any]:
    async with session_ctx() as session:
        result = await session.execute(select(UserPreference))
        prefs = result.scalars().all()
        out: dict[str, Any] = {}
        for p in prefs:
            val = p.value
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            out[p.key] = val
        return out


# ─── AutoForze Rules ──────────────────────────────────────────────────────────

async def get_habit_rules(trusted_only: bool = False) -> list[dict[str, Any]]:
    async with session_ctx() as session:
        stmt = select(AutoForzeHabitRule).order_by(AutoForzeHabitRule.confidence.desc())
        if trusted_only:
            stmt = stmt.where(
                and_(
                    AutoForzeHabitRule.confidence >= 0.7,
                    AutoForzeHabitRule.times_applied >= 3,
                )
            )
        result = await session.execute(stmt)
        rules = result.scalars().all()
        return [
            {
                "id":               rule.id,
                "name":             rule.name,
                "signal_type":      rule.signal_type,
                "description":      rule.description,
                "condition_data":   rule.condition_data or {},
                "action_data":      rule.action_data or {},
                "confidence":       rule.confidence,
                "times_applied":    rule.times_applied,
                "times_successful": rule.times_successful,
                "is_trusted":       rule.is_trusted,
            }
            for rule in rules
        ]


async def record_rule_outcome(rule_id: str, success: bool) -> None:
    """Update rule confidence using exponential moving average."""
    async with session_ctx() as session:
        result = await session.execute(
            select(AutoForzeHabitRule).where(AutoForzeHabitRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            return
        rule.times_applied += 1
        if success:
            rule.times_successful += 1
        # EMA with alpha=0.1 so recent outcomes influence confidence gradually
        new_confidence = (0.9 * rule.confidence) + (0.1 * (1.0 if success else 0.0))
        rule.confidence = round(min(max(new_confidence, 0.0), 1.0), 4)
        rule.updated_at = _utcnow()


async def save_behavior(
    rule_id: str,
    task_id: str | None,
    context_snapshot: dict[str, Any],
    outcome: str,
) -> None:
    async with session_ctx() as session:
        session.add(
            AutoForzeBehavior(
                id=str(uuid.uuid4()),
                rule_id=rule_id,
                task_id=_normalize_uuid(task_id) if task_id else None,
                context_snapshot=context_snapshot,
                outcome=outcome,
            )
        )


async def record_heartbeat(rules_active: int, reminders_sent: int, loop_ms: int) -> None:
    async with session_ctx() as session:
        session.add(
            AutoForzeHeartbeat(
                id=_new_id(),
                rules_active=rules_active,
                reminders_sent=reminders_sent,
                loop_ms=loop_ms,
            )
        )
