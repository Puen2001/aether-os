#!/usr/bin/env python3
"""dispatch-trace — append-only, privacy-preserving event logger for agent dispatch.

Wired as UserPromptSubmit + PostToolUse(Agent) + Stop hook in settings.json so it
fires every turn. Branches on hook_event_name. Writes one JSONL line per
invocation to ${CLAUDE_CONFIG_DIR}/logs/dispatch.jsonl (or ~/.config/personal-ai
when CLAUDE_CONFIG_DIR is unset).

Privacy: all user-authored text is sha256-hashed (16 hex chars) before write.
Only the agent type, vault name, lengths, and timestamps stay plaintext. No raw
prompt or instruction text ever leaves the originating session.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def config_dir() -> Path:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(cfg) if cfg else (Path.home() / ".config" / "personal-ai")


LOG_PATH = config_dir() / "logs" / "dispatch.jsonl"
HASH_LEN = 16


def h(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:HASH_LEN]


def vault_from_cwd(cwd: str) -> str:
    return Path(cwd).name if cwd else "unknown"


def build_record(payload: dict) -> dict | None:
    event = payload.get("hook_event_name", "")
    base = {
        "ts": time.time(),
        "session_id": payload.get("session_id", ""),
        "vault": vault_from_cwd(payload.get("cwd", "")),
    }

    if event == "UserPromptSubmit":
        prompt = payload.get("prompt", "") or ""
        return {
            **base,
            "event": "prompt",
            "prompt_hash": h(prompt),
            "prompt_len": len(prompt),
        }

    if event == "PostToolUse":
        if payload.get("tool_name") != "Agent":
            return None
        ti = payload.get("tool_input", {}) or {}
        return {
            **base,
            "event": "dispatch",
            "subagent_type": ti.get("subagent_type", "general-purpose"),
            "description_hash": h(ti.get("description", "") or ""),
            "dispatch_prompt_hash": h(ti.get("prompt", "") or ""),
            "dispatch_prompt_len": len(ti.get("prompt", "") or ""),
        }

    if event == "Stop":
        return {**base, "event": "turn_end"}

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        record = build_record(payload)
        if record is None:
            return 0
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, separators=(",", ":"))
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        # Never break the parent session over a trace failure.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
