#!/usr/bin/env python3
"""propose.py — AETHER OS memory proposal queue (deterministic, no model call).

Two subcommands, matching the contracts the hooks rely on:

  record --transcript <path> --session <id>
      Queue the just-ended session for the next-start memory-review pass.
      Writes one pending file. Silent. Fail-open (never raises to the caller).

  list
      Print the number of pending sessions as the FIRST stdout line (a bare
      integer), then a short human listing. The SessionStart hook reads line 1.

Pending files live in system/memory/pending/. No network, no API key, stdlib only.
The assistant is the judge at the next SessionStart — this script only queues.
"""
import sys
import os
import json
import argparse
import hashlib
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PENDING_DIR = os.path.join(HERE, "pending")


def _today():
    return datetime.date.today().isoformat()


def _condense(transcript_path, limit=12):
    """Best-effort: pull the last few user lines from a Claude Code .jsonl
    transcript as a hint for the review pass. Tolerates several shapes. Never raises."""
    hints = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                role = obj.get("role") or (obj.get("message") or {}).get("role")
                if role != "user":
                    continue
                content = obj.get("content") or (obj.get("message") or {}).get("content")
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = " ".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                text = " ".join(text.split())
                if text:
                    hints.append(text[:200])
    except Exception:
        pass
    return hints[-limit:]


def cmd_record(args):
    try:
        os.makedirs(PENDING_DIR, exist_ok=True)
        sid = args.session or hashlib.sha1(
            (args.transcript or _today()).encode()
        ).hexdigest()[:12]
        safe = "".join(c for c in sid if c.isalnum() or c in "-_") or "session"
        rec = {
            "session": sid,
            "transcript_path": args.transcript,
            "recorded_at": _today(),
            "hints": _condense(args.transcript) if args.transcript else [],
        }
        with open(os.path.join(PENDING_DIR, safe + ".json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
    except Exception:
        # fail-open: a memory hiccup must never break session close
        pass
    return 0


def cmd_list(_args):
    pending = []
    try:
        if os.path.isdir(PENDING_DIR):
            pending = sorted(f for f in os.listdir(PENDING_DIR) if f.endswith(".json"))
    except Exception:
        pending = []
    # CONTRACT: first stdout line is a bare integer count.
    print(len(pending))
    for f in pending:
        print(" -", f[:-5])
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="propose.py", add_help=True)
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("record", help="queue a finished session for review")
    r.add_argument("--transcript", default="")
    r.add_argument("--session", default="")
    sub.add_parser("list", help="print pending-session count (line 1) + listing")
    args = p.parse_args(argv)
    if args.cmd == "record":
        return cmd_record(args)
    if args.cmd == "list":
        return cmd_list(args)
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
