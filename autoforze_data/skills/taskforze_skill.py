#!/usr/bin/env python3
"""
TaskForze Skill for AutoForze
────────────────────────────
Allows AutoForze to create, list, and complete tasks via the TaskForze API.

Commands (natural language understood by AutoForze AI):
  - "create a task: <description>"
  - "list my tasks"
  - "mark task done"

Direct CLI usage (for cron / exec):
  python3 taskforze_skill.py task "Prepare slides"
  python3 taskforze_skill.py list
  python3 taskforze_skill.py done
  python3 taskforze_skill.py help
"""

import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

TASKFORZE_URL = "http://localhost:8000/autoforze/wa/message"
PHONE = "autoforze-skill"

def call_taskforze(command: str) -> str:
    """Send a command to the TaskForze backend and get a reply."""
    payload = json.dumps({"from": PHONE, "body": command}).encode()
    try:
        req = urllib.request.Request(
            TASKFORZE_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("reply", "No reply from TaskForze.")
    except urllib.error.URLError as e:
        return f"❌ Cannot reach TaskForze backend: {e}"
    except Exception as e:
        return f"❌ Error: {e}"


def main():
    args = sys.argv[1:]
    
    if not args:
        print(call_taskforze("#help"))
        return

    cmd = args[0].lower()

    if cmd in ("task", "create", "add"):
        description = " ".join(args[1:]) if len(args) > 1 else ""
        if not description:
            print("Usage: taskforze_skill.py task <description>")
            sys.exit(1)
        result = call_taskforze(f"#task {description}")
        print(result)

    elif cmd == "list":
        result = call_taskforze("#list")
        print(result)

    elif cmd in ("done", "complete", "finish"):
        result = call_taskforze("#done")
        print(result)

    elif cmd == "help":
        result = call_taskforze("#help")
        print(result)

    else:
        # Treat as natural language - send as-is
        full_msg = " ".join(args)
        result = call_taskforze(full_msg)
        print(result)


if __name__ == "__main__":
    main()
