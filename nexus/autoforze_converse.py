"""
AutoForze Conversational Builder — /autoforze/converse

POST /autoforze/converse
  Body: { session_id, message, history }
  Returns: { stage, reply, slots, ready, automation }

Stage machine:
  understand   → AI extracts slots from the user prompt
  clarify      → AI asks 1 clarifying question at a time
  confirm      → AI shows automation summary and asks "confirm?"
  done         → automation deployed
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autoforze", tags=["AutoForze"])

# ── In-memory session store ────────────────────────────────────────────────────
_SESSIONS: dict[str, dict] = {}

# ── Pydantic models ────────────────────────────────────────────────────────────
class ConverseRequest(BaseModel):
    session_id: str = ""
    message: str
    history: list[dict] = []


class ConverseResponse(BaseModel):
    session_id: str
    stage: str        # understand | clarify | confirm | done | error
    reply: str
    slots: dict
    ready: bool
    automation: dict


# ── Gemini: model fallback chain ───────────────────────────────────────────────
# Try newest → stable. Skips model if rate-limited (429).
_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]


def _gemini_call(system: str, contents_fn, *, json_mode: bool = False) -> str:
    """Try models in priority order. Returns raw text or raises."""
    from google import genai          # type: ignore
    from google.genai import types    # type: ignore

    client = genai.Client(vertexai=True, project="taskforze", location="us-central1")
    last_err = None

    for model in _MODELS:
        try:
            cfg: dict = dict(
                system_instruction=system,
                temperature=0.1 if json_mode else 0.3,
                max_output_tokens=1024,
            )
            if json_mode:
                cfg["response_mime_type"] = "application/json"

            response = client.models.generate_content(
                model=model,
                contents=contents_fn(types),
                config=types.GenerateContentConfig(**cfg),
            )
            return response.text or ""
        except Exception as exc:
            last_err = exc
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                logger.warning(f"[Gemini] {model} rate-limited, trying next model")
                continue
            raise  # non-quota errors bubble up

    raise RuntimeError(
        f"All Gemini models are rate-limited. Please wait ~1 minute and try again."
    )


def _gemini_chat(system: str, history: list[dict], user_msg: str) -> str:
    """Chat call with conversation history."""
    from google.genai import types  # type: ignore

    def build(types):
        contents = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))
        return contents

    return _gemini_call(system, build)


def _gemini_json(system: str, user_msg: str) -> dict:
    """Single-turn call expecting JSON output."""
    from google.genai import types  # type: ignore

    def build(types):
        return [types.Content(role="user", parts=[types.Part(text=user_msg)])]

    raw = _gemini_call(system, build, json_mode=True)
    return json.loads(raw or "{}")


# ── Slot extraction ────────────────────────────────────────────────────────────
_EXTRACT_SYSTEM = """
You are an automation intent extractor. Given a user description, extract these fields:
- trigger: what event starts the automation (e.g. "new WhatsApp message with #task", "scheduled daily 9am")
- action: what should happen (e.g. "create a task", "send a WhatsApp reply", "update a spreadsheet")
- channel: communication channel involved — must be exactly one of: whatsapp, slack, email, none
- condition: any filter or condition (e.g. "only if message starts with #task"), or null
- frequency: must be exactly one of: realtime, scheduled, one-time
- confidence: integer 0-100 (how sure you are you have enough info to build the automation)

Return ONLY valid JSON. No markdown. Example:
{
  "trigger": "incoming WhatsApp message starting with #task",
  "action": "create a task in TaskForze database",
  "channel": "whatsapp",
  "condition": "message body starts with #task",
  "frequency": "realtime",
  "confidence": 85
}
"""


def _extract_slots(text: str, existing: dict) -> dict:
    user_msg = f"Existing context: {json.dumps(existing)}\n\nUser said: {text}"
    try:
        result = _gemini_json(_EXTRACT_SYSTEM, user_msg)
        merged = {**existing}
        for k, v in result.items():
            if v is not None and str(v) not in ("", "null"):
                merged[k] = v
        return merged
    except Exception as exc:
        logger.error(f"[Slots] extraction failed: {exc}")
        return existing


# ── Clarification generation ───────────────────────────────────────────────────
_CLARIFY_SYSTEM = """
You are AutoForze, a friendly AI automation builder assistant.
You help users create automations step by step.

Given the user's intent and what you already know (slots), respond in ONE of two ways:
1. If confidence < 80: ask ONE short, specific clarifying question to fill in the most important missing piece.
2. If confidence >= 80: summarize what you'll build and ask for confirmation. Use the exact format:
   "Got it! I'll create an automation that: [trigger] → [action]. Shall I build it now? ✨"

Rules:
- Ask only ONE question at a time
- Be conversational and friendly
- Keep responses under 3 sentences
- Do not repeat information the user already gave

Current slots (what you know):
{slots}

Confidence: {confidence}/100
"""


def _generate_clarification(slots: dict, history: list[dict], user_msg: str) -> tuple[str, bool]:
    """Returns (reply_text, is_ready_to_build)."""
    conf = int(slots.get("confidence", 0))
    system = _CLARIFY_SYSTEM.format(
        slots=json.dumps({k: v for k, v in slots.items() if k != "confidence"}, indent=2),
        confidence=conf,
    )
    try:
        reply = _gemini_chat(system, history, user_msg)
        is_confirm = conf >= 80 and any(
            w in reply.lower()
            for w in ["shall i build", "ready to build", "build it now", "confirm", "shall i forge"]
        )
        return reply.strip(), is_confirm
    except Exception as exc:
        return f"⚠️ AI error: {exc}", False


# ── Build automation config ────────────────────────────────────────────────────
_BUILD_SYSTEM = """
You are AutoForze. Generate a structured automation configuration from the given slots.

Return ONLY valid JSON with this exact shape:
{
  "id": "<uuid4>",
  "name": "<human-readable name, max 6 words>",
  "description": "<one sentence describing the automation>",
  "trigger": { "type": "webhook|schedule|whatsapp|manual", "config": {} },
  "steps": [
    { "id": "step_1", "type": "condition|action|notify", "label": "<label>", "config": {} }
  ],
  "channel": "<whatsapp|slack|email|internal>",
  "status": "active"
}
"""


def _build_automation(slots: dict, history: list[dict]) -> dict:
    user_msg = f"Build an automation from these slots:\n{json.dumps(slots, indent=2)}"
    try:
        result = _gemini_json(_BUILD_SYSTEM, user_msg)
        if "id" not in result:
            result["id"] = str(uuid.uuid4())
        return result
    except Exception as exc:
        # Graceful fallback — always return a valid structure
        return {
            "id": str(uuid.uuid4()),
            "name": (slots.get("trigger", "My Automation") or "My Automation")[:40],
            "description": f"{slots.get('trigger', 'trigger')} → {slots.get('action', 'action')}",
            "trigger": {"type": "manual", "config": {}},
            "steps": [{"id": "step_1", "type": "action", "label": slots.get("action", "Run action"), "config": {}}],
            "channel": slots.get("channel", "internal"),
            "status": "active",
            "build_error": str(exc),
        }


# ── Main endpoint ──────────────────────────────────────────────────────────────
@router.post("/converse", response_model=ConverseResponse)
async def converse(req: ConverseRequest) -> ConverseResponse:
    sid     = req.session_id or str(uuid.uuid4())
    session = _SESSIONS.setdefault(sid, {
        "slots":     {},
        "stage":     "understand",
        "history":   [],
        "automation": {},
    })

    history  = req.history or session["history"]
    user_msg = req.message.strip()

    # ── Confirmed: build the automation ───────────────────────────────────────
    if session["stage"] == "confirm" and any(
        w in user_msg.lower()
        for w in ["yes", "go", "build", "confirm", "do it", "sure", "yep", "yeah", "ok", "✓"]
    ):
        automation = _build_automation(session["slots"], history)
        session.update(stage="done", automation=automation)
        session["history"].append({"role": "user",      "content": user_msg})

        steps_text = "\n".join(
            f"  {i+1}. {s.get('label', s.get('type', 'step'))}"
            for i, s in enumerate(automation.get("steps", []))
        )
        reply = (
            f"🚀 **{automation['name']}** is live!\n\n"
            f"Steps built:\n{steps_text}\n\n"
            f"Your automation is now active and monitoring for events."
        )
        session["history"].append({"role": "assistant", "content": reply})

        return ConverseResponse(
            session_id=sid, stage="done", reply=reply,
            slots=session["slots"], ready=True, automation=automation,
        )

    # ── Normal: extract slots → ask next question ─────────────────────────────
    session["slots"] = _extract_slots(user_msg, session["slots"])
    reply, is_ready  = _generate_clarification(session["slots"], history, user_msg)

    session["stage"] = "confirm" if is_ready else "clarify"
    session["history"].append({"role": "user",      "content": user_msg})
    session["history"].append({"role": "assistant", "content": reply})

    return ConverseResponse(
        session_id=sid,
        stage=session["stage"],
        reply=reply,
        slots=session["slots"],
        ready=is_ready,
        automation={},
    )


@router.delete("/converse/{session_id}")
async def clear_session(session_id: str):
    _SESSIONS.pop(session_id, None)
    return {"cleared": True}
