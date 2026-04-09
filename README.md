<div align="center">

<img src="https://img.shields.io/badge/-TaskForze-6C63FF?style=for-the-badge&logoColor=white" alt="TaskForze" />

# 🧠 TaskForze — NEXUS
### *The AI That Won't Let You Forget*

**A Production-Grade Multi-Agent AI Productivity System powered by Google Gemini**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Gemini AI](https://img.shields.io/badge/Gemini-2.5%20Flash-orange?style=flat-square&logo=google)](https://ai.google.dev)
[![AlloyDB](https://img.shields.io/badge/AlloyDB-PostgreSQL-4285F4?style=flat-square&logo=google-cloud)](https://cloud.google.com/alloydb)
[![Cloud Run](https://img.shields.io/badge/Cloud%20Run-Deployed-4285F4?style=flat-square&logo=google-cloud)](https://cloud.google.com/run)

---

### 🌐 **Live Demo**
**[https://taskforze-7k4ykvztvq-uc.a.run.app](https://taskforze-7k4ykvztvq-uc.a.run.app)**

---

</div>

## ✨ What Is TaskForze?

**TaskForze** is not a to-do app. It is an **autonomous, multi-agent AI system** that acts as your cognitive co-pilot — understanding your intent, managing your tasks, learning your habits, and proactively reminding you at the right moment through the right channel (WhatsApp, voice call, or the in-app chat).

Built for the **Google Cloud × AI hackathon**, it demonstrates:
- **5 collaborative AI agents** working in parallel via a central orchestrator
- **Self-learning AutoForze engine** that observes your behavior and adapts reminders accordingly
- **Omnichannel delivery**: WhatsApp Business API, voice calls (VAPI), and real-time WebSocket UI
- **AlloyDB + pgvector** for semantic memory — the agent literally *remembers* your notes
- **Google Workspace integration**: Calendar, Gmail, Drive sync — all from natural language

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TASKFORZE NEXUS                               │
│                                                                      │
│   ┌──────────────┐    ┌──────────────────────────────────────────┐  │
│   │  React UI    │◄──►│           NEXUS FastAPI Backend          │  │
│   │  (Chat +     │    │                                          │  │
│   │   Dashboard) │    │  ┌────────────────────────────────────┐  │  │
│   └──────────────┘    │  │      ORCHESTRATOR AGENT (Gemini)   │  │  │
│                       │  │  Decomposes intent → routes tasks  │  │  │
│   ┌──────────────┐    │  └──────┬──────┬──────┬──────┬───────┘  │  │
│   │  WhatsApp    │    │         │      │      │      │           │  │
│   │  Business    │◄──►│  ┌──────▼──┐ ┌─▼────┐ ┌────▼───┐       │  │
│   │  Cloud API   │    │  │CALENDAR │ │TASKS │ │ EMAIL  │       │  │
│   └──────────────┘    │  │  AGENT  │ │AGENT │ │ AGENT  │       │  │
│                       │  └─────────┘ └──────┘ └────────┘       │  │
│   ┌──────────────┐    │  ┌──────────────────────────────────┐   │  │
│   │  VAPI Voice  │◄──►│  │     AUTOFORZE ENGINE (Go/Python) │   │  │
│   │  Calls       │    │  │  Learn habits → Smart reminders  │   │  │
│   └──────────────┘    │  └──────────────────────────────────┘   │  │
│                       │                  │                       │  │
│                       │  ┌───────────────▼──────────────────┐   │  │
│                       │  │   AlloyDB (PostgreSQL + pgvector) │   │  │
│                       │  │   ScaNN vector index │ 10 tables  │   │  │
│                       │  └──────────────────────────────────┘   │  │
│                       └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 The 5 Agent System

| Agent | Responsibility | Key Tools |
|-------|---------------|-----------|
| **🎯 Orchestrator** | Understands natural language intent, decomposes it into tasks, routes to specialist agents | Gemini 2.5 Flash, intent parsing, workflow engine |
| **📅 Calendar Agent** | Reads / creates / updates Google Calendar events; detects conflicts | Google Calendar API v3, OAuth2 |
| **✅ Task Agent** | CRUD on tasks, dependency graph, priority scoring, cognitive load | AlloyDB, DAG engine, ScaNN |
| **📧 Email Agent** | Reads Gmail inbox, drafts replies, summarizes threads | Gmail API v1, Gemini summarization |
| **🔔 Reminder Agent** | Proactive reminder delivery; escalates from push → WhatsApp → voice if no ACK | WhatsApp Cloud API, VAPI, APScheduler |

### OrchestrationFlow

```
User: "Remind me about the contract review 2 hours before the deadline"
         │
         ▼
   Orchestrator (Gemini) → parse intent → detect deadline
         │
         ├─► Task Agent   → create task, set deadline, estimate effort
         │
         ├─► Calendar Agent → confirm event exists, pull exact time
         │
         └─► Reminder Agent → schedule reminder at T-2h
                              → learn from your ACK behavior (AutoForze)
```

---

## 🧬 AutoForze — The Self-Learning Engine

AutoForze is a custom intelligence module I built to make TaskForze *adaptive*. Written in Go and tightly integrated into the NEXUS backend, it runs as a lightweight sidecar process that:

1. **Observes patterns** — tracks when you snooze reminders, when you respond instantly, and what day/hour patterns exist
2. **Solidifies rules** — uses Exponential Moving Average to build confidence scores on habit rules
3. **Applies learned behavior** — automatically adjusts reminder timing, skips voice escalation for tasks you always ACK quickly, warns orchestrator on historically overloaded days

**Example habit rules it learns automatically:**
```json
{ "name": "Monday Morning Delay",      "confidence": 0.84 },
{ "name": "Contract Tasks Instant ACK", "confidence": 0.91 },
{ "name": "Tuesday Overload Warning",  "confidence": 0.76 }
```

### AutoForze WebSocket Chat

The UI includes a real-time AutoForze chat interface (WebSocket) that lets you converse naturally with the agent system without typing rigid commands.

---

## 📦 Full Feature List

### Task Management
- ✅ Create, update, complete, and delete tasks
- ✅ Dependency graph (DAG) with cycle detection — "Task B cannot start until Task A is done"
- ✅ Priority scoring: urgency × priority weight × effort hours
- ✅ Cognitive load calculator — warns when your day is overloaded
- ✅ Tag-based filtering and semantic note linking

### Reminders & Notifications
- ✅ Smart proactive reminders (not just alarms — *contextual* alerts)
- ✅ **WhatsApp Business API** integration — interactive button replies (Snooze / Done)
- ✅ **VAPI Voice Call** escalation — if WhatsApp isn't ACKed in 10 minutes, you get a call
- ✅ AutoForze adjusts lead times based on your historical behavior
- ✅ Snooze-aware: respects snooze windows, doesn't spam

### AI & Memory
- ✅ **Semantic search** on notes (AlloyDB ScaNN vector index, 768-dim embeddings)
- ✅ Gemini 2.5 Flash for all reasoning — intent parsing, summaries, triage
- ✅ Workflow replay — full trace of every agent decision stored in DB
- ✅ Context-aware: agent knows your calendar load before scheduling tasks

### Google Workspace Integration
- ✅ **Google Calendar**: read, create, update events across all calendars
- ✅ **Gmail**: read inbox, summarize threads, draft replies
- ✅ **Google Tasks** sync (bidirectional)
- ✅ **Google Drive**: sync task/note data as backup
- ✅ OAuth 2.0 flow with refresh token management

### Infrastructure
- ✅ **AlloyDB** (PostgreSQL 15 + pgvector + ScaNN) on Google Cloud
- ✅ **AlloyDB Auth Proxy** — no public DB exposure
- ✅ **Alembic migrations** — dialect-aware (PostgreSQL + SQLite fallback for dev)
- ✅ **Cloud Run** deployment with health checks
- ✅ Structured logging via `structlog` + optional Logfire
- ✅ Docker + Cloud Build CI/CD ready

---

## 🗂️ Project Structure

```
TaskForze/
├── nexus/                      # Core Python backend
│   ├── main.py                 # FastAPI app (20+ endpoints)
│   ├── config.py               # Pydantic-settings (12-factor)
│   ├── db/
│   │   ├── models.py           # SQLAlchemy ORM (10 tables, AlloyDB types)
│   │   ├── session.py          # Async engine, Auth Proxy support, SQLite fallback
│   │   └── engine.py           # Legacy shim (backward-compat re-exports)
│   ├── agents/
│   │   ├── orchestrator.py     # Central AI agent, workflow decomposition
│   │   ├── calendar_agent.py   # Google Calendar operations
│   │   ├── task_agent.py       # Task CRUD + dependency resolution
│   │   ├── email_agent.py      # Gmail operations
│   │   └── reminder_agent.py   # Notification dispatch + escalation
│   ├── tools/
│   │   ├── db_tools.py         # Unified async DB API (40+ functions)
│   │   ├── dependency_graph.py # DAG engine with topological sort
│   │   ├── google_auth.py      # OAuth2 token management
│   │   ├── gmail_tools.py      # Gmail API wrapper
│   │   └── drive_tools.py      # Drive sync
│   ├── routers/
│   │   ├── chat.py             # SSE streaming + sync chat
│   │   ├── webhooks.py         # WhatsApp, Twilio, VAPI webhooks
│   │   └── workflows.py        # Workflow replay + status
│   ├── scheduler/
│   │   └── reminder_scheduler.py  # APScheduler — runs reminder loop
│   ├── autoforze_bridge.py     # AutoForze ↔ NEXUS integration layer
│   └── autoforze_converse.py   # WebSocket chat endpoint for AutoForze UI
│
├── autoforze/                  # AutoForze sidecar (custom Go module)
│   └── cmd/autoforze/          # CLI agent with cron, skills, channels
│
├── autoforze_data/             # AutoForze runtime config & skills
│   ├── config.json             # Channels, LLM, tools configuration
│   └── skills/
│       └── taskforze_skill.py  # AutoForze skill: create/list/complete tasks
│
├── db/
│   └── alloydb_bootstrap.sql   # Full AlloyDB schema (extensions, indexes, functions, seed)
│
├── alembic/
│   ├── env.py                  # Async-aware Alembic environment
│   └── versions/
│       └── 0001_initial_schema.py  # Dialect-aware migration (PG + SQLite)
│
├── scripts/
│   ├── setup_alloydb.sh        # One-command AlloyDB provisioner (12 steps)
│   └── start_proxy.sh          # AlloyDB Auth Proxy manager
│
├── frontend/                   # React + Vite UI
│   └── src/
│       ├── components/         # Task board, Chat, Calendar view, AutoForze chat
│       └── pages/              # Dashboard, Auth, Workflows
│
├── Dockerfile                  # Production multi-stage build
├── Procfile                    # Cloud Run entry point
└── .env.example                # Template for all 20+ env vars
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Google Cloud account with billing enabled
- Google API key (Gemini)

### 1. Clone & Bootstrap

```bash
git clone https://github.com/yourusername/taskforze
cd taskforze

# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
# Required
GOOGLE_API_KEY=AIza...your_gemini_api_key...

# Database (SQLite for dev, AlloyDB for prod)
DATABASE_URL=sqlite+aiosqlite:///./nexus_dev.db

# Optional — WhatsApp push notifications
WHATSAPP_PHONE_ID=your_meta_phone_id
WHATSAPP_TOKEN=your_whatsapp_token
USER_WHATSAPP_NUMBER=+91xxxxxxxxxx

# Optional — Voice escalation
VAPI_API_KEY=your_vapi_key

# Optional — Google Calendar/Gmail
FRONTEND_URL=http://localhost:3000
WEBHOOK_BASE_URL=http://localhost:8000
```

### 3. Run Database Migrations

```bash
# Creates all 10 tables in local SQLite (no cloud required)
python -m alembic upgrade head
```

### 4. Start the Backend

```bash
uvicorn nexus.main:app --reload --port 8000
```

### 5. Start the Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 6. Start AutoForze (optional — adds habit learning + chat)

```bash
cd autoforze_data
../autoforze/bin/autoforze start
# → AutoForze WebSocket on ws://localhost:18790
```

---

## ☁️ Deployment (Google Cloud Run)

### Option A — One-Command Deploy

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy backend to Cloud Run
gcloud run deploy taskforze-nexus \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=AIza...,DATABASE_URL=postgresql+asyncpg://..." \
  --memory 1Gi \
  --cpu 1
```

### Option B — AlloyDB + Full Production Stack

```bash
# Provision AlloyDB cluster, instance, schema, migrations in one script
DB_PASSWORD=your_secret \
PROJECT_ID=your-project \
./scripts/setup_alloydb.sh
```

This script handles all 12 steps:
1. Enable APIs (AlloyDB, Cloud Run, Secret Manager)
2. Create AlloyDB cluster (`taskforze-cluster`)
3. Create primary instance (2 vCPUs)
4. Install AlloyDB Auth Proxy
5. Start proxy on `127.0.0.1:5432`
6. Create DB user + database
7. Apply full bootstrap schema (extensions, indexes, functions)
8. Update `.env` with connection string
9. Run `alembic upgrade head`
10. Verify all 10 tables
11. Seed preferences + sample tasks
12. Print verification report

**Hosted URL:**
```
https://taskforze-7k4ykvztvq-uc.a.run.app
```

---

## 💬 Usage Guide

### Via Web Chat UI

Open the dashboard and type naturally:

```
"Remind me to review the investor contract 2 hours before the deadline"
"What's my cognitive load tomorrow?"
"Create a task: prepare pitch deck, high priority, due Friday"
"Show me what's coming up in the next 6 hours"
"What did I note about the Series A term sheet?"  ← uses semantic search
```

### Via WhatsApp

Send messages to your configured number:
```
#task Prepare board presentation
#list
#done
```

Or use the interactive buttons that arrive with reminders:
- **✅ Done** → marks the task complete
- **⏰ Snooze 30m** → delays the reminder

### Via AutoForze Chat (WebSocket)

The AutoForze interface (built into the UI) accepts full natural language and can:
- Build multi-step automations
- Schedule cron-based tasks
- Execute shell skills
- Search the web for context before creating tasks

---

## 🗄️ Database Schema

10 tables, production-ready on AlloyDB PostgreSQL with pgvector:

| Table | Purpose |
|-------|---------|
| `tasks` | Tasks with priority, deadline, effort, cognitive load score, tags |
| `task_dependencies` | DAG edges — which task blocks which |
| `notes` | Long-form notes with 768-dim vector embeddings for semantic search |
| `workflow_runs` | Full trace of every multi-agent workflow |
| `active_workflows` | Current running workflow per user |
| `reminder_log` | History of every reminder sent, ACK'd, snoozed |
| `user_preferences` | JSON key-value store for user settings |
| `autoforze_habit_rules` | Learned behavioral patterns with confidence scores |
| `autoforze_behaviors` | Individual behavior records that feed rule learning |
| `autoforze_heartbeat` | Health metrics for the AutoForze loop |

### AlloyDB-Specific Features

- **`pgvector`** extension — 768-dimensional note embeddings
- **`alloydb_scann`** extension — 10× faster approximate nearest-neighbor search than plain pgvector
- **`task_priority_score()`** stored function — server-side urgency calculation
- **`get_upcoming_tasks()`** — single-query join across tasks + reminders + snooze state
- **`semantic_search()`** — ScaNN-accelerated cosine similarity lookup
- **`compute_daily_load()`** — server-side cognitive load aggregation
- GIN indexes on `tags` and `content` for full-text search
- Partial indexes on `status` for hot-path query performance

---

## 🔌 API Reference

All endpoints available at `/docs` (Swagger UI) when running locally.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | SSE streaming chat with agent reasoning visible |
| `POST` | `/chat/sync` | Non-streaming chat (for webhooks, integrations) |
| `GET` | `/tasks` | List tasks with priority scores |
| `POST` | `/tasks` | Create task directly |
| `GET` | `/workflows` | List all past workflow runs |
| `GET` | `/workflows/{id}` | Replay a specific workflow with full trace |
| `GET` | `/agents/status` | Live status of all 5 agents |
| `GET` | `/calendar/events` | Upcoming Google Calendar events |
| `POST` | `/webhook/whatsapp` | Handle WhatsApp messages and button replies |
| `POST` | `/webhook/vapi` | Handle VAPI voice call outcomes |
| `GET` | `/auth/status` | Check Google OAuth connection |
| `GET` | `/auth/login` | Start Google OAuth2 flow |
| `POST` | `/auth/setup` | Save OAuth credentials (one-time) |
| `POST` | `/api/drive/sync` | Trigger Google Drive data sync |
| `GET` | `/health` | Health check (for Cloud Run) |
| `WS` | `/autoforze/ws` | AutoForze real-time chat WebSocket |

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | ✅ | Gemini API key |
| `DATABASE_URL` | ✅ | `sqlite+aiosqlite:///./dev.db` or AlloyDB URL |
| `GEMINI_MODEL` | — | Default: `gemini-2.5-flash` |
| `VERTEX_PROJECT_ID` | — | GCP project for Vertex AI embeddings |
| `VERTEX_LOCATION` | — | Default: `asia-south1` |
| `WHATSAPP_PHONE_ID` | — | Meta Business phone number ID |
| `WHATSAPP_TOKEN` | — | Meta WhatsApp Cloud API token |
| `WHATSAPP_APP_SECRET` | — | For webhook signature verification |
| `WHATSAPP_VERIFY_TOKEN` | — | Meta webhook verification token |
| `USER_WHATSAPP_NUMBER` | — | Your personal number (e.g., `+91xxxxxxxxxx`) |
| `VAPI_API_KEY` | — | Voice call escalation via VAPI |
| `FRONTEND_URL` | — | Default: `http://localhost:3000` |
| `WEBHOOK_BASE_URL` | — | Public URL for OAuth callbacks |
| `LOGFIRE_TOKEN` | — | Pydantic Logfire observability token |

---

## 🔐 Security

- **Database**: Never exposed to public internet — all connections via AlloyDB Auth Proxy
- **OAuth tokens**: Stored in local filesystem (`token.json`), never logged
- **WhatsApp webhooks**: HMAC-SHA256 signature verification on every request
- **CORS**: Explicit allowlist — no wildcard in production
- **Secrets**: All via environment variables / Secret Manager — none in code
- **Input validation**: Pydantic models at every API boundary

---

## 🧪 Testing

```bash
# Run the DB smoke test
python3 -c "
import asyncio
from nexus.tools.db_tools import create_task, get_tasks, set_preference
async def test():
    t = await create_task({'title': 'Test task', 'priority': 3})
    print('Created:', t['id'])
    tasks = await get_tasks(limit=5)
    print(f'Found {len(tasks)} tasks')
asyncio.run(test())
"

# API health check
curl http://localhost:8000/health | python3 -m json.tool

# Verify all tables exist
python3 -m alembic current
```

---

## 🛣️ Roadmap

- [ ] **Mobile app** (React Native with push notifications)
- [ ] **Habit pattern visualization** dashboard (AutoForze analytics)
- [ ] **Multi-user support** with team task sharing
- [ ] **Slack / Telegram** notification channels
- [ ] **Obsidian vault sync** for note management
- [ ] **LLM-generated weekly retrospectives** sent every Sunday

---

## 🙏 Built With

| Technology | Role |
|-----------|------|
| **Google Gemini 2.5 Flash** | Core reasoning for all 5 agents |
| **Google AlloyDB** | Production PostgreSQL with pgvector + ScaNN |
| **Google Cloud Run** | Serverless deployment |
| **AlloyDB Auth Proxy** | Secure DB connectivity |
| **FastAPI** | High-performance async API framework |
| **SQLAlchemy 2.0 (async)** | ORM with full async support |
| **Alembic** | Database migration management |
| **Gemini Embedding 001** | 768-dim note embeddings |
| **WhatsApp Business Cloud API** | Push notification delivery |
| **VAPI** | AI voice call escalation |
| **Google Calendar / Gmail API** | Workspace integration |
| **APScheduler** | Async scheduled reminder loop |
| **AutoForze** | Custom self-learning habit engine (Go) |
| **React + Vite** | Frontend UI |
| **structlog** | Structured production logging |

---

## 👨‍💻 Author

**Balaraj**
Google APAC Hackathon 2026 — *TaskForze: The AI That Won't Let You Forget*

> *"Built in India, designed to think like a brilliant, never-forgetful personal assistant."*

---

<div align="center">

**Built entirely by Balaraj · Google APAC Hackathon 2026**

</div>
