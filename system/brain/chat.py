#!/usr/bin/env python3
"""Minimal text REPL over the brain router — backend-agnostic.

  python3 system/brain/chat.py

Type a message, get a reply, on whatever backend BRAIN_PROVIDER selects
(api / cmd / claude / codex). This is the text-terminal assistant that custom
launchers (see `./aether launcher`) open. Ctrl-D or "exit" to quit.

The assistant is personalized from introduction.md (override with CHAT_PERSONA).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("PAI_ROOT") or Path(__file__).resolve().parents[2])
ROUTER = ROOT / "system" / "brain" / "router.py"


def load_persona() -> str:
    override = os.environ.get("CHAT_PERSONA")
    if override:
        return override
    intro = ROOT / "introduction.md"
    if intro.exists():
        return intro.read_text(errors="replace")[:4000]
    return ""


def main() -> int:
    persona = load_persona()
    session = ""
    provider = os.environ.get("BRAIN_PROVIDER", "claude")
    print(f"AETHER chat ({provider}) — type a message; Ctrl-D or 'exit' to quit.")
    while True:
        try:
            line = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            break

        cmd = [sys.executable, str(ROUTER), "--prompt", line, "--persona", persona]
        if session:
            cmd += ["--resume", session]
        try:
            completed = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        except Exception as exc:  # noqa: BLE001 - REPL must never crash on one turn
            print(f"[error] {exc}", file=sys.stderr)
            continue

        out = completed.stdout.strip()
        if not out:
            print(f"[no reply] {completed.stderr.strip()[:300]}", file=sys.stderr)
            continue
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            print(out)
            continue

        if payload.get("session_id"):
            session = payload["session_id"]
        reply = (payload.get("result") or "").strip()
        print(reply or f"[error] {payload.get('error', 'empty result')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
