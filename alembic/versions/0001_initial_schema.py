"""
Alembic initial migration — TaskForze AlloyDB schema v1.

Strategy:
  • AlloyDB / PostgreSQL → run the full alloydb_bootstrap.sql (ScaNN, PL/pgSQL, etc.)
  • SQLite (dev)         → create tables inline with SQLite-compatible DDL
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision      = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on    = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        _run_alloydb_bootstrap()
    else:
        _create_sqlite_tables()


def downgrade() -> None:
    tables = [
        "autoforze_heartbeat",
        "autoforze_behaviors",
        "autoforze_habit_rules",
        "reminder_log",
        "active_workflows",
        "workflow_runs",
        "notes",
        "task_dependencies",
        "user_preferences",
        "tasks",
    ]
    for table in tables:
        op.drop_table(table)


# ─── PostgreSQL / AlloyDB path ────────────────────────────────────────────────

def _run_alloydb_bootstrap() -> None:
    """Execute the AlloyDB bootstrap SQL (idempotent — IF NOT EXISTS throughout)."""
    from pathlib import Path

    bootstrap_sql = (
        Path(__file__).resolve().parent.parent.parent / "db" / "alloydb_bootstrap.sql"
    )
    if not bootstrap_sql.exists():
        raise FileNotFoundError(
            f"AlloyDB bootstrap SQL not found: {bootstrap_sql}\n"
            "Run from the TaskForze project root or check db/alloydb_bootstrap.sql"
        )

    sql_text = bootstrap_sql.read_text()
    # Split on statement boundaries so SQLAlchemy executes each one
    for stmt in _split_sql(sql_text):
        if stmt.strip():
            op.execute(sa.text(stmt))


def _split_sql(sql: str) -> list[str]:
    """
    Naive statement splitter that handles $$ dollar-quoted functions.
    Returns individual SQL statements ready for execution.
    """
    statements: list[str] = []
    current: list[str] = []
    in_dollar_quote = False

    for line in sql.splitlines():
        stripped = line.rstrip()

        # Track entry/exit of $$ dollar-quoted blocks (PL/pgSQL functions)
        dollar_count = stripped.count("$$")
        if dollar_count % 2 != 0:
            in_dollar_quote = not in_dollar_quote

        current.append(line)

        # Statement ends at ; only when we're not inside a dollar-quoted block
        if not in_dollar_quote and stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []

    # Anything leftover (no trailing semicolon)
    if current:
        leftover = "\n".join(current).strip()
        if leftover:
            statements.append(leftover)

    return statements


# ─── SQLite / Dev path ────────────────────────────────────────────────────────

def _create_sqlite_tables() -> None:
    """Minimal SQLite-compatible table creation for local dev."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("priority", sa.Integer(), server_default="3"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effort_hours", sa.Float(), server_default="1.0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("cognitive_load_score", sa.Float(), server_default="0"),
        sa.Column("linked_workflow_id", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_intent", sa.Text(), server_default=""),
        sa.Column("plan", sa.JSON(), server_default="[]"),
        sa.Column("context", sa.JSON(), server_default="{}"),
        sa.Column("agent_outputs", sa.JSON(), server_default="{}"),
        sa.Column("trace", sa.JSON(), server_default="[]"),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Text(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on", sa.Text(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "notes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("title", sa.Text(), server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), server_default="[]"),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("linked_task_id", sa.Text(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_event_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "active_workflows",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("workflow_id", sa.Text(), sa.ForeignKey("workflow_runs.id"), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "reminder_log",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("task_id", sa.Text(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_ms", sa.Integer(), nullable=True),
    )
    op.create_table(
        "user_preferences",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "autoforze_habit_rules",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("signal_type", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_data", sa.JSON(), server_default="{}"),
        sa.Column("action_data", sa.JSON(), server_default="{}"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("times_applied", sa.Integer(), server_default="0"),
        sa.Column("times_successful", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "autoforze_behaviors",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("rule_id", sa.Text(), sa.ForeignKey("autoforze_habit_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.Text(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), server_default="{}"),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("solidified_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "autoforze_heartbeat",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("rules_active", sa.Integer(), server_default="0"),
        sa.Column("reminders_sent", sa.Integer(), server_default="0"),
        sa.Column("loop_ms", sa.Integer(), server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
