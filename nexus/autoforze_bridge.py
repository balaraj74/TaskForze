"""AutoForze Bridge — FastAPI router.

Endpoints:
  POST /autoforze/start          → start automation (detects WhatsApp)
  POST /autoforze/stop           → terminate running process
  GET  /autoforze/status         → running / offline / whatsapp_auth
  GET  /autoforze/stream         → SSE log stream
  POST /autoforze/whatsapp/start → start WhatsApp QR session explicitly
  GET  /autoforze/whatsapp/qr    → SSE: streams QR + auth events
  GET  /autoforze/whatsapp/ready → whether WA is authenticated
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autoforze", tags=["AutoForze"])

# ── Global process handles ────────────────────────────────────────────
autoforze_process: subprocess.Popen | None = None
whatsapp_process: subprocess.Popen | None = None

# Shared WhatsApp state (read by both the SSE stream and the main stream)
_wa_state: dict = {
    "qr": None,           # base64 PNG data URL
    "authenticated": False,
    "ready": False,
    "phone": None,
    "error": None,
    "logs": [],
}

# ── Pydantic models ───────────────────────────────────────────────────
class StartRequest(BaseModel):
    prompt: str = ""


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

# Paths to the real AutoForze binary and config
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_AUTOFORZE_BIN = os.path.join(_ROOT, "bin", "autoforze")
_AUTOFORZE_DATA = os.path.join(_ROOT, "autoforze_data")
_AUTOFORZE_CFG = os.path.join(_AUTOFORZE_DATA, "config.json")
_SKILL_SCRIPT = os.path.join(_AUTOFORZE_DATA, "skills", "taskforze_skill.py")


def _needs_whatsapp(prompt: str) -> bool:
    kw = ["whatsapp", "whats app", "wa message", "send whatsapp"]
    return any(k in prompt.lower() for k in kw)


def _skill_runner_cmd(prompt: str) -> list[str]:
    """
    Build a command that runs the TaskForze skill directly.
    Used for simple prompts so AutoForze doesn't need to be fully started.
    """
    lp = prompt.strip().lower()
    if lp.startswith("#task ") or lp.startswith("create task") or lp.startswith("add task"):
        desc = prompt.split(" ", 1)[1] if " " in prompt else prompt
        return [sys.executable, _SKILL_SCRIPT, "task", desc]
    elif lp.startswith("#list") or "list task" in lp:
        return [sys.executable, _SKILL_SCRIPT, "list"]
    elif lp.startswith("#done") or "complete task" in lp or "mark done" in lp:
        return [sys.executable, _SKILL_SCRIPT, "done"]
    elif lp.startswith("#help"):
        return [sys.executable, _SKILL_SCRIPT, "help"]
    else:
        return [sys.executable, _SKILL_SCRIPT] + prompt.split()


# ─────────────────────────────────────────────────────────────────────
# WHATSAPP BACKGROUND READER
# ─────────────────────────────────────────────────────────────────────

async def _read_whatsapp_process():
    """Background task: reads stdout from whatsapp_service.js and populates _wa_state."""
    global whatsapp_process
    if not whatsapp_process:
        return
    loop = asyncio.get_event_loop()
    while True:
        if whatsapp_process is None or whatsapp_process.poll() is not None:
            break
        line = await loop.run_in_executor(
            None, whatsapp_process.stdout.readline
        )
        if not line:
            await asyncio.sleep(0.1)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            etype = event.get("type", "")
            if etype == "qr":
                _wa_state["qr"] = event.get("qr")
                _wa_state["error"] = None
            elif etype == "authenticated":
                _wa_state["authenticated"] = True
            elif etype == "ready":
                _wa_state["ready"] = True
                _wa_state["phone"] = event.get("phone")
            elif etype == "error":
                _wa_state["error"] = event.get("message")
            elif etype == "log":
                _wa_state["logs"].append(event.get("message", ""))
        except json.JSONDecodeError:
            _wa_state["logs"].append(line)


# ─────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_autoforze(req: StartRequest):
    global autoforze_process

    if autoforze_process and autoforze_process.poll() is None:
        return {"status": "running", "message": "AutoForze is already running."}

    needs_wa = _needs_whatsapp(req.prompt)

    if needs_wa:
        # Signal to the SSE stream that WhatsApp auth is required first.
        # The actual automation starts only after WA is ready (triggered by frontend).
        return {
            "status": "whatsapp_required",
            "message": "WhatsApp detected in your automation. Please authenticate via QR code.",
        }

    # Non-WhatsApp: launch real AutoForze or skill runner
    try:
        if os.path.exists(_AUTOFORZE_BIN) and os.path.exists(_AUTOFORZE_CFG):
            # ── Real AutoForze binary ──────────────────────────────────
            logger.info(f"[AutoForze] Launching real binary: {_AUTOFORZE_BIN}")
            env = os.environ.copy()
            env["AUTOFORZE_CONFIG"] = _AUTOFORZE_CFG
            env["HOME"] = _AUTOFORZE_DATA  # data directory
            env["GEMINI_API_KEY"] = env.get("GOOGLE_API_KEY", "")
            cmd = [_AUTOFORZE_BIN, "start", "--config", _AUTOFORZE_CFG]
        else:
            # ── Fallback: direct skill runner ──────────────────────────
            logger.warning("[AutoForze] Binary not found; using skill runner fallback")
            cmd = _skill_runner_cmd(req.prompt)

        autoforze_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy() | {"GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
                                     "GEMINI_API_KEY": os.environ.get("GOOGLE_API_KEY", "")},
        )
        return {"status": "started", "message": "AutoForze started successfully."}
    except Exception as exc:
        logger.error("autoforze_start_failed", exc_info=exc)
        return {"status": "error", "message": str(exc)}


@router.post("/start_with_whatsapp")
async def start_with_whatsapp(req: StartRequest):
    """Called after WhatsApp is authenticated to run the full automation."""
    global autoforze_process

    if autoforze_process and autoforze_process.poll() is None:
        return {"status": "running", "message": "AutoForze is already running."}

    try:
        if os.path.exists(_AUTOFORZE_BIN) and os.path.exists(_AUTOFORZE_CFG):
            cmd = [_AUTOFORZE_BIN, "start", "--config", _AUTOFORZE_CFG]
        else:
            cmd = _skill_runner_cmd(req.prompt)

        autoforze_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy() | {"GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
                                     "GEMINI_API_KEY": os.environ.get("GOOGLE_API_KEY", "")},
        )
        return {"status": "started", "message": "Automation started with WhatsApp."}
    except Exception as exc:
        logger.error("autoforze_wa_start_failed", exc_info=exc)
        return {"status": "error", "message": str(exc)}



@router.post("/stop")
async def stop_autoforze():
    global autoforze_process, whatsapp_process
    stopped = []
    if autoforze_process and autoforze_process.poll() is None:
        autoforze_process.terminate()
        autoforze_process = None
        stopped.append("automation")
    if whatsapp_process and whatsapp_process.poll() is None:
        whatsapp_process.terminate()
        whatsapp_process = None
        _wa_state.update({"qr": None, "authenticated": False, "ready": False, "phone": None, "error": None, "logs": []})
        stopped.append("whatsapp")
    if stopped:
        return {"status": "stopped", "stopped": stopped}
    return {"status": "offline", "message": "Nothing was running."}


@router.get("/status")
async def autoforze_status():
    global autoforze_process
    running = autoforze_process and autoforze_process.poll() is None
    return {
        "status": "running" if running else "offline",
        "whatsapp": {
            "authenticated": _wa_state["authenticated"],
            "ready": _wa_state["ready"],
            "phone": _wa_state["phone"],
        },
    }


# ── SSE: main log stream ──────────────────────────────────────────────
async def tail_logs() -> AsyncGenerator[str, None]:
    global autoforze_process
    if not autoforze_process or autoforze_process.poll() is not None:
        yield 'data: {"type": "error", "message": "AutoForze is not running."}\n\n'
        return

    loop = asyncio.get_event_loop()
    while True:
        if autoforze_process is None or autoforze_process.poll() is not None:
            if autoforze_process and autoforze_process.stdout:
                for line in autoforze_process.stdout.readlines():
                    line = line.strip()
                    if line:
                        yield f"data: {line}\n\n"
            break

        line = await loop.run_in_executor(None, autoforze_process.stdout.readline)
        if line:
            yield f"data: {line.strip()}\n\n"
        else:
            await asyncio.sleep(0.05)


@router.get("/stream")
async def stream_autoforze_logs():
    return StreamingResponse(tail_logs(), media_type="text/event-stream")


# ── WhatsApp endpoints ────────────────────────────────────────────────

@router.post("/whatsapp/start")
async def start_whatsapp_session():
    """Start the whatsapp-web.js Node process and begin reading events."""
    global whatsapp_process

    if whatsapp_process and whatsapp_process.poll() is None:
        return {"status": "running", "message": "WhatsApp session already active."}

    # Reset state
    _wa_state.update({"qr": None, "authenticated": False, "ready": False, "phone": None, "error": None, "logs": []})

    script_path = os.path.join(os.path.dirname(__file__), "whatsapp_service.js")
    if not os.path.exists(script_path):
        return {"status": "error", "message": "whatsapp_service.js not found."}

    # node_modules lives at the TaskForze root (parent of nexus/)
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    node_modules_path = os.path.join(root_dir, "node_modules")
    env = os.environ.copy()
    env["NODE_PATH"] = node_modules_path

    node_bin = "node"
    whatsapp_process = subprocess.Popen(
        [node_bin, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        cwd=root_dir,   # run from root so require() resolves node_modules
    )

    # Launch background reader coroutine
    asyncio.create_task(_read_whatsapp_process())

    return {"status": "started", "message": "WhatsApp session starting…"}


async def _wa_sse_generator() -> AsyncGenerator[str, None]:
    """SSE generator: pushes QR + status updates to the browser."""
    sent_qr: str | None = None
    sent_ready = False
    timeout = 180  # 3 minutes max
    elapsed = 0.0

    while elapsed < timeout:
        await asyncio.sleep(0.5)
        elapsed += 0.5

        # Push any new log lines
        while _wa_state["logs"]:
            msg = _wa_state["logs"].pop(0)
            yield f'data: {json.dumps({"type": "log", "message": msg})}\n\n'

        # Push QR if new
        current_qr = _wa_state.get("qr")
        if current_qr and current_qr != sent_qr:
            sent_qr = current_qr
            yield f'data: {json.dumps({"type": "qr", "qr": current_qr})}\n\n'

        # Error
        if _wa_state.get("error"):
            yield f'data: {json.dumps({"type": "error", "message": _wa_state["error"]})}\n\n'
            return

        # Ready
        if _wa_state["ready"] and not sent_ready:
            sent_ready = True
            yield f'data: {json.dumps({"type": "ready", "phone": _wa_state["phone"]})}\n\n'
            return

    yield f'data: {json.dumps({"type": "error", "message": "QR timeout — please try again."})}\n\n'


@router.get("/whatsapp/qr")
async def whatsapp_qr_stream():
    """SSE stream: emits QR code, authentication, and ready events."""
    return StreamingResponse(_wa_sse_generator(), media_type="text/event-stream")


@router.get("/whatsapp/ready")
async def whatsapp_ready():
    return {
        "ready": _wa_state["ready"],
        "authenticated": _wa_state["authenticated"],
        "phone": _wa_state["phone"],
    }


# ── Incoming WhatsApp message handler (called by whatsapp_service.js) ─────────

class WaMessageRequest(BaseModel):
    from_: str = ""
    body: str = ""

    class Config:
        populate_by_name = True

    # Allow "from" as the JSON key (reserved word in Python)
    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict) and "from" in obj and "from_" not in obj:
            obj = {**obj, "from_": obj.pop("from")}
        return super().model_validate(obj, **kwargs)


@router.post("/wa/message")
async def handle_wa_message(request: Request):
    """
    Called by whatsapp_service.js when an inbound WhatsApp message arrives.
    Routes through the same command layer as the Meta Cloud API webhook.
    Returns { reply: "<text>" }
    """
    try:
        body = await request.json()
        sender = body.get("from", "")
        text = body.get("body", "").strip()

        logger.info(f"[WA-MSG] from=+{sender} body={text[:80]}")

        # Import the command router from webhooks
        from nexus.routers.webhooks import _route_message
        reply = await _route_message(text, sender=sender)

        return {"reply": reply}
    except Exception as exc:
        logger.error(f"[WA-MSG] handler error: {exc}")
        return {"reply": f"⚠️ Error: {exc}"}


