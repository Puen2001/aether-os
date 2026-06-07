#!/usr/bin/env python3
"""statusline.py — Claude Code status line (compact).

Renders:  <Model> · <bar> NN% · <dir> · <branch>● · 5h NN% 7d NN% · $cost · <elapsed>

Segments auto-omit when their data is absent (rate_limits before first call,
cost=0, no git repo, etc.). Reads the statusLine JSON contract on stdin,
defensively. Pure stdout, stdlib only, fast. Git state comes from one
`status --porcelain=v2 --branch` call, timeout-guarded.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# --- ANSI -----------------------------------------------------------------
R = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"

SEP = f" {DIM}·{R} "


def lvl_color(pct: float) -> str:
    if pct >= 80:
        return RED
    if pct >= 50:
        return YELLOW
    return GREEN


def bar(pct: float, cells: int = 3) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * cells))
    col = lvl_color(pct)
    return f"{col}{'█' * filled}{R}{DIM}{'░' * (cells - filled)}{R}"


def fmt_elapsed(ms: float) -> str:
    s = int(ms // 1000)
    if s < 60:
        return f"{s}s"
    m = s // 60
    if m < 60:
        return f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h{m}m"


def git_segment(cwd: str) -> str | None:
    """Branch name + a red ● when dirty, from one porcelain call. None if not a repo."""
    if not cwd or not os.path.isdir(cwd):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain=v2", "--branch"],
            capture_output=True, text=True, timeout=0.5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    branch, dirty = None, False
    for line in out.stdout.splitlines():
        if line.startswith("# branch.head "):
            branch = line[len("# branch.head "):].strip()
        elif line and not line.startswith("#"):
            dirty = True
    if not branch:
        return None
    if branch == "(detached)":
        branch = "detached"
    mark = f"{RED}●{R}" if dirty else ""
    return f"{MAGENTA}{branch}{R}{mark}"


def main() -> int:
    try:
        d = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    segs: list[str] = []

    # model (compact — name only)
    model = (d.get("model") or {}).get("display_name") or "Claude"
    segs.append(f"{BOLD}{model}{R}")

    # context usage bar + %
    cw = d.get("context_window") or {}
    pct = cw.get("used_percentage")
    pct = float(pct) if isinstance(pct, (int, float)) else 0.0
    segs.append(f"{bar(pct)} {lvl_color(pct)}{pct:.0f}%{R}")

    # directory
    cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or ""
    segs.append(f"{CYAN}{os.path.basename(cwd.rstrip('/')) or '~'}{R}")

    # git branch + dirty
    g = git_segment(cwd)
    if g:
        segs.append(g)

    # rate limits (5h / 7d) — omit if not present yet
    rl = d.get("rate_limits") or {}
    parts = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = rl.get(key) or {}
        p = w.get("used_percentage")
        if isinstance(p, (int, float)):
            parts.append(f"{DIM}{label}{R} {lvl_color(p)}{p:.0f}%{R}")
    if parts:
        segs.append(" ".join(parts))

    # session cost
    cost = (d.get("cost") or {}).get("total_cost_usd")
    if isinstance(cost, (int, float)) and cost > 0:
        segs.append(f"{GREEN}${cost:.2f}{R}")

    # wall-clock elapsed
    dur = (d.get("cost") or {}).get("total_duration_ms")
    if isinstance(dur, (int, float)) and dur > 0:
        segs.append(f"{DIM}{fmt_elapsed(dur)}{R}")

    sys.stdout.write(SEP.join(segs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
