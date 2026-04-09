"""Webhook endpoints for WhatsApp Cloud API, legacy Twilio, and Vapi.

Command protocol (works on Meta WA Cloud API + Twilio legacy):
  #task <description>   → Create a task via TaskAgent, Gemini analysis, WA reply with summary
  #done                 → Mark the most urgent pending task as done
  #list                 → List today's top 5 actionable tasks
  #help                 → Show available commands
  <any other text>      → Full Orchestrator pipeline (calendar, notes, tasks, etc.)
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import PlainTextResponse

from nexus.agents import task_agent
from nexus.agents.orchestrator import process
from nexus.middleware.security import (
    validate_vapi_webhook,
    validate_whatsapp_webhook,
    verify_whatsapp_webhook,
)
from nexus.tools import db_tools
from nexus.tools.gemini_tools import generate
from nexus.tools.retry import send_whatsapp_with_retry
from nexus.tools.whatsapp_tools import wa_client

router = APIRouter(prefix="/webhook", tags=["Webhooks"])
logger = structlog.get_logger(__name__)

# ─── WhatsApp Cloud API ──────────────────────────────────────────────────────


@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
) -> int:
    """Meta webhook verification handshake."""
    return await verify_whatsapp_webhook(hub_mode, hub_verify_token, hub_challenge)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict[str, Any]:
    """Handle inbound WhatsApp text messages and button replies."""
    await validate_whatsapp_webhook(request)
    payload = await request.json()
    parsed = wa_client.parse_webhook(payload)
    if not parsed:
        return {"status": "ignored"}

    sender = parsed.get("from", "")

    # Interactive button replies (done / snooze)
    if parsed.get("callback_data"):
        result = await _handle_button_reply(parsed["callback_data"])
        await send_whatsapp_with_retry(sender, result.get("message", "Done."))
        return {"status": "ok", **result}

    # Text messages — route through command layer
    if parsed.get("text"):
        reply = await _route_message(parsed["text"], sender=sender)
        await send_whatsapp_with_retry(sender, reply[:1500])
        return {"status": "ok", "reply": reply}

    return {"status": "ignored"}


# ─── Twilio legacy ───────────────────────────────────────────────────────────


@router.post("/twilio")
async def twilio_webhook(
    Body: str = Form(""),
    From: str = Form(""),
) -> PlainTextResponse:
    """Legacy compatibility endpoint for existing Twilio sandbox demos."""
    logger.info("twilio_webhook", body=Body, from_=From)
    reply = await _route_message(Body, sender=From)
    return PlainTextResponse(reply[:1500])


# ─── Vapi ────────────────────────────────────────────────────────────────────


@router.post("/vapi")
async def vapi_webhook(request: Request) -> dict[str, Any]:
    """Handle Vapi call outcomes for done/snooze intents."""
    await validate_vapi_webhook(request)
    body = await request.json()
    logger.info("vapi_webhook", type=body.get("type"))

    transcript = (body.get("transcript") or "").lower()
    metadata = body.get("metadata", {})
    task_id = metadata.get("task_id")

    if task_id:
        if "done" in transcript or "complete" in transcript:
            await db_tools.mark_acknowledged(task_id)
            await db_tools.update_task(task_id, {"status": "done"})
        elif "snooze" in transcript:
            await db_tools.snooze_task(task_id, minutes=30)
        else:
            await db_tools.log_reminder({"task_id": task_id, "channel": "voice", "outcome": "no_response"})

    return {"status": "ok"}


# ─── Command router ───────────────────────────────────────────────────────────


async def _route_message(text: str, *, sender: str = "") -> str:
    """Route an inbound message to the right handler based on prefix command."""
    stripped = text.strip()
    lowered = stripped.lower()

    # ── #task <description> ──────────────────────────────────────────────────
    if lowered.startswith("#task"):
        return await _handle_task_command(stripped[5:].strip(), sender=sender)

    # ── #done ────────────────────────────────────────────────────────────────
    if lowered.startswith("#done"):
        return await _handle_done_command()

    # ── #list ────────────────────────────────────────────────────────────────
    if lowered.startswith("#list"):
        return await _handle_list_command()

    # ── #help ────────────────────────────────────────────────────────────────
    if lowered.startswith("#help"):
        return _help_text()

    # ── fallback → full orchestrator pipeline ────────────────────────────────
    return await _process_chat_message(stripped)


# ─── Command handlers ──────────────────────────────────────────────────────


async def _handle_task_command(description: str, *, sender: str = "") -> str:
    """Create a real task via TaskAgent and return a Gemini-analysed reply."""
    if not description:
        return (
            "⚠️ Please tell me what the task is.\n"
            "Example: *#task Fix the login bug by Friday*"
        )

    logger.info("whatsapp_task_command", description=description[:120], sender=sender)

    try:
        # 1. Create the task through TaskAgent (stores in DB + syncs Google Tasks)
        result = await task_agent.run(f"create task: {description}")
        created = result.get("created_task") or {}
        task_title = created.get("title", description[:60])
        task_id = created.get("id", "")

        # 2. Ask Gemini to produce a brief analysis / next-step suggestion
        analysis = await _gemini_task_analysis(task_title, description)

        # 3. Build the reply
        lines = [
            f"✅ *Task created!*",
            f"📌 *{task_title}*",
        ]
        if created.get("deadline"):
            lines.append(f"⏰ Due: {_fmt_deadline(created['deadline'])}")
        if created.get("priority"):
            lines.append(f"🔥 Priority: {created['priority']}/5")
        lines.append("")
        lines.append(f"🤖 *Gemini says:*\n{analysis}")
        if task_id:
            lines.append(f"\n_Reply *#done* when finished._")

        return "\n".join(lines)

    except Exception as exc:
        logger.error("task_command_error", exc=str(exc))
        return f"❌ Could not create task: {exc}"


async def _handle_done_command() -> str:
    """Mark the most urgent pending task as done."""
    upcoming = await db_tools.get_upcoming_tasks(window_minutes=180)
    if not upcoming:
        ranked = await db_tools.get_ranked_tasks(limit=1)
        if not ranked:
            return "🎉 No pending tasks found — you're all clear!"
        upcoming = ranked

    task = upcoming[0]
    await db_tools.mark_acknowledged(task["id"])
    await db_tools.update_task(task["id"], {"status": "done"})
    return f"✅ Marked *{task['title']}* as done!"


async def _handle_list_command() -> str:
    """Return a formatted list of today's top 5 tasks."""
    tasks = await db_tools.get_actionable_tasks(limit=5)
    if not tasks:
        return "🎉 No pending tasks — inbox zero achieved!"

    lines = ["📋 *Your top tasks:*", ""]
    priority_emoji = {5: "🔴", 4: "🟠", 3: "🟡", 2: "🟢", 1: "⚪"}
    for i, t in enumerate(tasks, 1):
        emoji = priority_emoji.get(t.get("priority", 3), "🟡")
        deadline_str = f" — due {_fmt_deadline(t['deadline'])}" if t.get("deadline") else ""
        lines.append(f"{i}. {emoji} {t['title']}{deadline_str}")

    lines.append("\n_Reply *#done* to mark the top task complete._")
    return "\n".join(lines)


def _help_text() -> str:
    return textwrap.dedent("""
        🤖 *TaskForze Commands*

        *#task <description>* — Create a new task
        Example: `#task Prepare slides for Monday meeting`

        *#done* — Mark your most urgent task as done

        *#list* — See your top 5 pending tasks

        *#help* — Show this help message

        _You can also send any free text and I'll handle it intelligently!_
    """).strip()


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _gemini_task_analysis(title: str, description: str) -> str:
    """Ask Gemini to briefly analyse the task and suggest a first step."""
    try:
        prompt = (
            f"A user just created a task via WhatsApp:\n"
            f"Title: {title}\n"
            f"Description: {description}\n\n"
            f"In 2-3 sentences, give a helpful analysis:\n"
            f"1. Why this task matters\n"
            f"2. The most important first step to take\n"
            f"Keep it concise and practical. No bullet points."
        )
        return await generate(prompt)
    except Exception:
        return "Break this into smaller steps and tackle the hardest part first."


def _fmt_deadline(deadline: str | None) -> str:
    if not deadline:
        return "—"
    # Trim to date only for readability
    return str(deadline)[:10] if deadline else "—"


async def _handle_button_reply(callback_data: str) -> dict[str, Any]:
    action, _, explicit_task_id = callback_data.partition(":")
    task = await db_tools.get_task_by_id(explicit_task_id) if explicit_task_id else None
    if task is None:
        upcoming = await db_tools.get_upcoming_tasks(window_minutes=180)
        if not upcoming:
            return {"status": "ok", "message": "No pending tasks found"}
        task = upcoming[0]

    if action == "ack":
        await db_tools.mark_acknowledged(task["id"])
        await db_tools.update_task(task["id"], {"status": "done"})
        return {"status": "ok", "message": f"✅ Marked *{task['title']}* done"}
    if action == "snooze_15":
        result = await db_tools.snooze_task(task["id"], minutes=15)
        return {"status": "ok", "message": f"⏰ Snoozed until {result['new_deadline']}"}
    if action == "snooze_60":
        result = await db_tools.snooze_task(task["id"], minutes=60)
        return {"status": "ok", "message": f"⏰ Snoozed 1 hour until {result['new_deadline']}"}
    return {"status": "ignored", "message": "Unknown action"}


async def _process_chat_message(message: str) -> str:
    """Route free-text messages through the full multi-agent orchestrator."""
    final_result: dict[str, Any] = {}
    async for event in process(message):
        if event.get("type") == "result":
            final_result = event
    return final_result.get("summary") or "Nexus processed your message."
