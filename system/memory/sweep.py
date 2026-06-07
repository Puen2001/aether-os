#!/usr/bin/env python3
"""sweep.py — AETHER OS memory-governance sweep.

Scans memory entries for facts that need review and reports how many are
"flagged" (expired, low-confidence, or ungoverned). Detection only — it never
edits or deletes an entry; you review the flagged list yourself.

  sweep.py [--dry-run] [DIR]

DIR defaults to system/memory/entries/. With --dry-run it prints a summary dict
(the SessionStart cadence hook scrapes 'flagged': N from it) and does NOT touch
the last-run marker. Without --dry-run it also writes today's date to
system/memory/.last-sweep and prints a human-readable report.

Frontmatter expected per entry (see system/memory/README.md):
  confidence: high | med | low
  expires_after_check: YYYY-MM-DD
stdlib only, no network.
"""
import sys
import os
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "entries")
LAST = os.path.join(HERE, ".last-sweep")


def _today():
    return datetime.date.today()


def _parse_frontmatter(path):
    """Tiny YAML-ish frontmatter reader (key: value between --- fences)."""
    fm = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:
        return fm
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip().lower()] = v.strip().strip('"').strip("'")
    return fm


def _flag(path):
    """Return a reason string if the entry should be flagged, else None."""
    fm = _parse_frontmatter(path)
    conf = fm.get("confidence", "").lower()
    exp = fm.get("expires_after_check", "")
    if not conf or not exp:
        return "ungoverned (missing confidence or expiry)"
    if conf == "low":
        return "low confidence"
    try:
        if datetime.date.fromisoformat(exp) < _today():
            return "expired %s" % exp
    except Exception:
        return "unparseable expiry %r" % exp
    return None


def scan(directory):
    flagged = []
    scanned = 0
    try:
        files = sorted(
            f for f in os.listdir(directory)
            if f.endswith(".md") and f.lower() != "memory.md"
        )
    except Exception:
        files = []
    for f in files:
        scanned += 1
        reason = _flag(os.path.join(directory, f))
        if reason:
            flagged.append((f, reason))
    return scanned, flagged


def main(argv=None):
    p = argparse.ArgumentParser(prog="sweep.py")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("dir", nargs="?", default=DEFAULT_DIR)
    args = p.parse_args(argv)

    scanned, flagged = scan(args.dir)
    summary = {"scanned": scanned, "flagged": len(flagged)}

    if args.dry_run:
        # CONTRACT: emit a dict containing 'flagged': N (hook scrapes it).
        print(summary)
        return 0

    print("AETHER OS memory sweep —", _today().isoformat())
    print(summary)
    if flagged:
        print("\nflagged for review:")
        for f, reason in flagged:
            print("  - %s — %s" % (f, reason))
        print("\nReview each: re-attest (confidence + fresh expiry), edit, or delete.")
    else:
        print("nothing flagged — memory is fresh.")
    try:
        with open(LAST, "w", encoding="utf-8") as fh:
            fh.write(_today().isoformat() + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
