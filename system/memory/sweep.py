#!/usr/bin/env python3
"""sweep.py — AETHER OS memory-governance sweep.

Scans memory entries for facts that need review and reports how many are
"flagged". Detection only — it never edits or deletes an entry; you review the
flagged list yourself.

  sweep.py [--dry-run] [DIR]

Flags an entry when it is:
  - expired       : expires_after_check is in the past
  - low confidence: confidence: low
  - ungoverned    : missing confidence or expires_after_check
  - superseded    : another entry declares `supersedes: <this>`
  - contradicted  : it sits on a `contradicts:` edge with another entry
  - duplicate     : its body content-hash matches another entry's (SHA-256)

Typed relationships (idea adapted from agentmemory) live in frontmatter:
  supersedes: <name|title>     # this entry replaces that one -> that one is stale
  contradicts: <name|title>    # the two conflict -> both flagged for review
  extends:    <name|title>     # informational edge, not flagged

DIR defaults to system/memory/entries/. With --dry-run it prints a summary dict
(the SessionStart cadence hook scrapes 'flagged': N) and changes nothing. Without
--dry-run it also writes today's date to system/memory/.last-sweep and prints a
human-readable report. stdlib only, no network.
"""
import sys
import os
import argparse
import datetime
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(HERE, "entries")
LAST = os.path.join(HERE, ".last-sweep")
_EDGE_KEYS = ("supersedes", "contradicts", "extends")


def _today():
    return datetime.date.today()


def _split(path):
    """Return (frontmatter_text, body_text). Either may be empty."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:
        return "", ""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    body_start = text.find("\n", end + 1)
    return text[3:end], (text[body_start + 1:] if body_start != -1 else "")


def _frontmatter(fm_text):
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip().lower()] = v.strip().strip('"').strip("'")
    return fm


def _norm_key(s):
    """Normalize an entry reference for matching (drop .md, lowercase, strip)."""
    s = (s or "").strip().strip('"').strip("'")
    if s.lower().endswith(".md"):
        s = s[:-3]
    return s.lower()


def _body_hash(body):
    norm = " ".join(body.split())  # whitespace-insensitive
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() if norm else ""


def _self_reason(fm):
    """Per-entry flag from its own frontmatter (expired / low / ungoverned)."""
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
    """Return (scanned, flagged) where flagged is a list of (name, reason)."""
    try:
        files = sorted(
            f for f in os.listdir(directory)
            if f.endswith(".md") and f.lower() != "memory.md"
        )
    except Exception:
        files = []

    entries = []   # (name, fm, body_hash)
    keys = {}      # normalized identity -> name  (stem + title)
    for f in files:
        name = f[:-3]
        fm_text, body = _split(os.path.join(directory, f))
        fm = _frontmatter(fm_text)
        entries.append((name, fm, _body_hash(body)))
        keys[_norm_key(name)] = name
        if fm.get("title"):
            keys[_norm_key(fm["title"])] = name

    reasons = {}  # name -> reason (first wins, but we keep it simple)

    def add(name, reason):
        reasons.setdefault(name, reason)

    # per-entry self reasons + typed edges
    by_hash = {}
    for name, fm, bhash in entries:
        r = _self_reason(fm)
        if r:
            add(name, r)
        if bhash:
            by_hash.setdefault(bhash, []).append(name)
        for k in _EDGE_KEYS:
            if k not in fm:
                continue
            target = keys.get(_norm_key(fm[k]))
            if not target or target == name:
                continue
            if k == "supersedes":
                add(target, "superseded by %s" % name)
            elif k == "contradicts":
                add(name, "contradicts %s" % target)
                add(target, "contradicts %s" % name)
            # 'extends' is informational — not flagged

    # duplicate bodies
    for bhash, names in by_hash.items():
        if len(names) > 1:
            for n in names:
                others = ", ".join(x for x in names if x != n)
                add(n, "duplicate of %s" % others)

    scanned = len(entries)
    flagged = sorted(reasons.items())
    return scanned, flagged


def main(argv=None):
    p = argparse.ArgumentParser(prog="sweep.py")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("dir", nargs="?", default=DEFAULT_DIR)
    args = p.parse_args(argv)

    scanned, flagged = scan(args.dir)
    summary = {"scanned": scanned, "flagged": len(flagged)}

    if args.dry_run:
        # CONTRACT: emit a dict containing 'flagged': N (the hook scrapes it).
        print(summary)
        return 0

    print("AETHER OS memory sweep —", _today().isoformat())
    print(summary)
    if flagged:
        print("\nflagged for review:")
        for name, reason in flagged:
            print("  - %s — %s" % (name, reason))
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
