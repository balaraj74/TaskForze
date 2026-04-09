-- ═══════════════════════════════════════════════════════════════════════════
-- TASKFORZE — AlloyDB Bootstrap Script
-- Run this ONCE on a fresh AlloyDB database.
-- Connect via:  psql "host=127.0.0.1 port=5432 dbname=taskforze user=taskforze_user"
--              (AlloyDB Auth Proxy must be running locally)
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 0. Extensions ──────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS alloydb_scann;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- ─── 1. Core Tables ─────────────────────────────────────────────────────────

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title                TEXT NOT NULL,
    description          TEXT DEFAULT '',
    priority             INT  DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    deadline             TIMESTAMPTZ,
    effort_hours         FLOAT DEFAULT 1.0,
    status               TEXT DEFAULT 'pending'
                             CHECK (status IN ('pending','in_progress','done','blocked')),
    cognitive_load_score FLOAT DEFAULT 0.0,
    linked_workflow_id   UUID,
    tags                 TEXT[] DEFAULT '{}',
    created_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at           TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Task dependency DAG
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id    UUID REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on UUID REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on),
    CONSTRAINT no_self_dep CHECK (task_id != depends_on)
);

-- Notes with AlloyDB ScaNN vector embeddings
CREATE TABLE IF NOT EXISTS notes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT DEFAULT '',
    content         TEXT NOT NULL,
    tags            TEXT[] DEFAULT '{}',
    embedding       vector(768),
    linked_task_id  UUID REFERENCES tasks(id) ON DELETE SET NULL,
    linked_event_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Workflow audit log
CREATE TABLE IF NOT EXISTS workflow_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_intent   TEXT DEFAULT '',
    plan          JSONB DEFAULT '[]'::jsonb,
    context       JSONB DEFAULT '{}'::jsonb,
    agent_outputs JSONB DEFAULT '{}'::jsonb,
    trace         JSONB DEFAULT '[]'::jsonb,
    status        TEXT DEFAULT 'running'
                      CHECK (status IN ('running','completed','failed')),
    duration_ms   INT,
    created_at    TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at  TIMESTAMPTZ
);

-- Concurrent workflow guard
CREATE TABLE IF NOT EXISTS active_workflows (
    user_id     TEXT PRIMARY KEY,
    workflow_id UUID REFERENCES workflow_runs(id),
    intent      TEXT,
    started_at  TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Reminder escalation history
CREATE TABLE IF NOT EXISTS reminder_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES tasks(id) ON DELETE CASCADE NOT NULL,
    channel         TEXT NOT NULL CHECK (channel IN ('whatsapp','voice')),
    sent_at         TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    outcome         TEXT CHECK (outcome IN ('ack','snoozed','escalated','no_response')),
    snooze_until    TIMESTAMPTZ,
    delivery_ms     INT
);

-- User preference key-value store
CREATE TABLE IF NOT EXISTS user_preferences (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ─── 2. AutoForze Tables ────────────────────────────────────────────────────

-- HabitEngine learned rules
CREATE TABLE IF NOT EXISTS autoforze_habit_rules (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    signal_type      TEXT CHECK (signal_type IN (
                         'time_pattern','instant_ack','overload_detected',
                         'channel_preference','day_of_week_pattern',
                         'snooze_loop','deadline_proximity','novel_context'
                     )),
    description      TEXT,
    condition_data   JSONB DEFAULT '{}'::jsonb,
    action_data      JSONB DEFAULT '{}'::jsonb,
    confidence       FLOAT DEFAULT 0.5 CHECK (confidence BETWEEN 0.0 AND 1.0),
    times_applied    INT DEFAULT 0,
    times_successful INT DEFAULT 0,
    is_trusted       BOOLEAN GENERATED ALWAYS AS
                         (confidence >= 0.7 AND times_applied >= 3) STORED,
    created_at       TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at       TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Solidified behavior memories
CREATE TABLE IF NOT EXISTS autoforze_behaviors (
    id               TEXT PRIMARY KEY,
    rule_id          TEXT REFERENCES autoforze_habit_rules(id) ON DELETE SET NULL,
    task_id          UUID REFERENCES tasks(id) ON DELETE SET NULL,
    context_snapshot JSONB DEFAULT '{}'::jsonb,
    outcome          TEXT,
    solidified_at    TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Runtime heartbeat metrics
CREATE TABLE IF NOT EXISTS autoforze_heartbeat (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rules_active   INT DEFAULT 0,
    reminders_sent INT DEFAULT 0,
    loop_ms        INT DEFAULT 0,
    recorded_at    TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ─── 3. Indexes ─────────────────────────────────────────────────────────────

-- Tasks
CREATE INDEX IF NOT EXISTS idx_tasks_status
    ON tasks(status) WHERE status != 'done';

CREATE INDEX IF NOT EXISTS idx_tasks_deadline
    ON tasks(deadline ASC) WHERE deadline IS NOT NULL AND status != 'done';

CREATE INDEX IF NOT EXISTS idx_tasks_priority
    ON tasks(priority DESC, deadline ASC);

CREATE INDEX IF NOT EXISTS idx_tasks_workflow
    ON tasks(linked_workflow_id) WHERE linked_workflow_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_tags
    ON tasks USING gin(tags);

-- Notes: AlloyDB ScaNN vector index (cosine, 100 leaves)
CREATE INDEX IF NOT EXISTS notes_scann_idx
    ON notes USING scann (embedding cosine)
    WITH (num_leaves = 100);

-- Notes: full-text search
CREATE INDEX IF NOT EXISTS idx_notes_content_fts
    ON notes USING gin(to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS idx_notes_task
    ON notes(linked_task_id) WHERE linked_task_id IS NOT NULL;

-- Workflows
CREATE INDEX IF NOT EXISTS idx_workflow_status
    ON workflow_runs(status, created_at DESC);

-- Reminders
CREATE INDEX IF NOT EXISTS idx_reminder_task
    ON reminder_log(task_id, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_reminder_pending
    ON reminder_log(task_id) WHERE acknowledged_at IS NULL;

-- Habit rules
CREATE INDEX IF NOT EXISTS idx_habit_trusted
    ON autoforze_habit_rules(confidence DESC) WHERE confidence >= 0.7;

CREATE INDEX IF NOT EXISTS idx_habit_signal
    ON autoforze_habit_rules(signal_type);

-- ─── 4. Helper Functions ────────────────────────────────────────────────────

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tasks_updated_at ON tasks;
CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS notes_updated_at ON notes;
CREATE TRIGGER notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS habit_rules_updated_at ON autoforze_habit_rules;
CREATE TRIGGER habit_rules_updated_at
    BEFORE UPDATE ON autoforze_habit_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Priority score: urgency × priority × effort
CREATE OR REPLACE FUNCTION task_priority_score(
    p_deadline     TIMESTAMPTZ,
    p_priority     INT,
    p_effort_hours FLOAT
) RETURNS FLOAT AS $$
DECLARE
    hours_left FLOAT;
    urgency    FLOAT;
BEGIN
    IF p_deadline IS NULL THEN RETURN 0.0; END IF;
    hours_left := GREATEST(EXTRACT(EPOCH FROM (p_deadline - NOW())) / 3600, 0.1);
    urgency    := 1.0 / hours_left;
    RETURN ROUND((urgency * p_priority * p_effort_hours)::NUMERIC, 4);
END;
$$ LANGUAGE plpgsql;

-- Upcoming tasks for the reminder loop
CREATE OR REPLACE FUNCTION get_upcoming_tasks(
    window_minutes INT DEFAULT 130
)
RETURNS TABLE (
    id                 UUID,
    title              TEXT,
    deadline           TIMESTAMPTZ,
    priority           INT,
    status             TEXT,
    effort_hours       FLOAT,
    minutes_left       FLOAT,
    priority_score     FLOAT,
    last_reminder_sent TIMESTAMPTZ,
    acknowledged_at    TIMESTAMPTZ,
    snooze_until       TIMESTAMPTZ,
    last_outcome       TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id, t.title, t.deadline,
        t.priority, t.status, t.effort_hours,
        EXTRACT(EPOCH FROM (t.deadline - NOW())) / 60 AS minutes_left,
        task_priority_score(t.deadline, t.priority, t.effort_hours),
        rl.sent_at,
        rl.acknowledged_at,
        rl.snooze_until,
        rl.outcome
    FROM tasks t
    LEFT JOIN LATERAL (
        SELECT sent_at, acknowledged_at, snooze_until, outcome
        FROM reminder_log
        WHERE task_id = t.id
        ORDER BY sent_at DESC
        LIMIT 1
    ) rl ON true
    WHERE t.status NOT IN ('done', 'blocked')
      AND t.deadline IS NOT NULL
      AND t.deadline <= NOW() + (window_minutes * INTERVAL '1 minute')
      AND t.deadline >= NOW() - INTERVAL '10 minutes'
    ORDER BY t.deadline ASC;
END;
$$ LANGUAGE plpgsql;

-- Daily cognitive load
CREATE OR REPLACE FUNCTION compute_daily_load(
    target_date DATE DEFAULT CURRENT_DATE
) RETURNS FLOAT AS $$
DECLARE
    task_count INT;
    avg_effort FLOAT;
    total_load FLOAT;
BEGIN
    SELECT COUNT(*), COALESCE(AVG(COALESCE(effort_hours, 1.0)), 0)
    INTO task_count, avg_effort
    FROM tasks
    WHERE DATE(deadline) = target_date
      AND status != 'done';

    total_load := (task_count * 0.5) + (avg_effort * 1.5);
    RETURN ROUND(total_load::NUMERIC, 2);
END;
$$ LANGUAGE plpgsql;

-- Semantic note search via ScaNN
CREATE OR REPLACE FUNCTION semantic_search(
    query_embedding vector(768),
    result_limit    INT DEFAULT 5
)
RETURNS TABLE (
    id             UUID,
    title          TEXT,
    content        TEXT,
    tags           TEXT[],
    score          FLOAT,
    linked_task_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id, n.title, n.content, n.tags,
        (1 - (n.embedding <=> query_embedding))::FLOAT AS score,
        n.linked_task_id
    FROM notes n
    WHERE n.embedding IS NOT NULL
    ORDER BY n.embedding <=> query_embedding
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- ─── 5. Seed Data ────────────────────────────────────────────────────────────

INSERT INTO user_preferences (key, value) VALUES
    ('reminder_lead_time_minutes', '30'),
    ('voice_escalation_enabled',   'true'),
    ('whatsapp_number',            '"+91xxxxxxxxxx"'),
    ('timezone',                   '"Asia/Kolkata"'),
    ('working_hours_start',        '9'),
    ('working_hours_end',          '21'),
    ('cognitive_load_threshold',   '8'),
    ('weekly_retro_day',           '"sunday"'),
    ('morning_brief_hour',         '8')
ON CONFLICT (key) DO NOTHING;

INSERT INTO tasks (title, description, priority, deadline, effort_hours, status) VALUES
(
    'Review investor contract',
    'Legal review of Series A term sheet',
    5, NOW() + INTERVAL '30 minutes', 2.0, 'pending'
),
(
    'Finalize pitch deck',
    'Add traction slides and financial projections',
    4, NOW() + INTERVAL '2 hours', 3.0, 'pending'
),
(
    'Submit hackathon project',
    'Final submission with demo video',
    5, NOW() + INTERVAL '24 hours', 4.0, 'in_progress'
),
(
    'Weekly team sync prep',
    'Prepare agenda and action items',
    3, NOW() + INTERVAL '3 days', 1.0, 'pending'
)
ON CONFLICT DO NOTHING;

INSERT INTO autoforze_habit_rules
    (id, name, signal_type, description, condition_data, action_data,
     confidence, times_applied, times_successful)
VALUES
(
    'rule-monday-delay',
    'Monday Morning Delay',
    'time_pattern',
    'Snooze rate 78% on Mondays 8-9am. Delay by 45 minutes.',
    '{"day_of_week": 1, "hour_start": 8, "hour_end": 9}'::jsonb,
    '{"delay_minutes": 45}'::jsonb,
    0.84, 12, 10
),
(
    'rule-contract-instant',
    'Contract Tasks Instant ACK',
    'instant_ack',
    'Contract tasks ACKed in <3min 91% of time. Skip voice escalation.',
    '{"title_keywords": ["contract", "legal", "agreement"]}'::jsonb,
    '{"skip_voice_escalation": true}'::jsonb,
    0.91, 11, 10
),
(
    'rule-tuesday-overload',
    'Tuesday Overload Warning',
    'overload_detected',
    'Tuesday load > 8 consistently. Warn orchestrator before scheduling.',
    '{"day_of_week": 2, "load_threshold": 8}'::jsonb,
    '{"warn_orchestrator": true, "suggest_reschedule": true}'::jsonb,
    0.76, 8, 6
)
ON CONFLICT (id) DO NOTHING;
