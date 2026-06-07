# Memory engine

Governed, auditable long-term memory for your assistant. Two small, deterministic,
stdlib-only Python scripts — **no model calls, no network, no API key.** This is a
reference implementation; extend it to taste.

## The loop

1. **A session ends** → the `SessionEnd` hook calls `propose.py record …`, which queues
   the session under `pending/` for review. Nothing is written to memory yet.
2. **A session starts** → the `SessionStart` hook calls `propose.py list`; if sessions
   are pending, you get a one-line nudge. Say *"review proposals"* and the assistant
   reads the queued session(s), proposes memory entries, and writes only the ones you
   confirm. **Propose, don't write silently.**
3. **Periodically** → `sweep.py` flags entries that have gone stale so you can re-attest,
   edit, or delete them. The `SessionStart` cadence hook reminds you when a sweep is due.

## Entry format

Each memory is one Markdown file in `entries/` with frontmatter:

```yaml
---
title: <human-readable>
type: user | feedback | project | reference
confidence: high | med | low      # high = you stated/confirmed it; low = the AI's guess
expires_after_check: YYYY-MM-DD    # a freshness horizon, or a hard real-world date
created: YYYY-MM-DD
source: <where this came from>
# optional typed relationships to another entry (by filename stem or title):
supersedes: <name|title>           # this entry replaces that one -> that one is flagged stale
contradicts: <name|title>          # the two conflict -> both flagged for review
extends:    <name|title>           # informational edge (not flagged)
---

<the fact, in one or two lines>
```

`MEMORY.md` (in `entries/`, optional) is a one-line-per-entry index loaded at session start.

## What the sweep flags

- **expired** — `expires_after_check` is in the past.
- **low confidence** — `confidence: low` (the AI's own inference; verify before relying).
- **ungoverned** — missing `confidence` or `expires_after_check`.
- **superseded** — another entry declares `supersedes: <this>` (the old one is now stale).
- **contradicted** — two entries sit on a `contradicts:` edge (both surfaced to reconcile).
- **duplicate** — two entries share the same body content-hash (SHA-256, whitespace-insensitive).

The `propose.py` queue also dedups deterministically: identical session content recorded within a
10-minute window is queued once, not twice (no model call). Typed edges + content-hash dedup are
ideas adapted from agentmemory, kept file-based and stdlib-only.

```bash
python3 system/memory/sweep.py            # full report + records the run date
python3 system/memory/sweep.py --dry-run  # just the counts, changes nothing
python3 system/memory/sweep.py --dry-run examples/memory   # see it flag the stale example
```

## Contracts (don't break these — the hooks depend on them)

- `propose.py list` → **first stdout line is a bare integer** (pending count).
- `propose.py record --transcript <p> --session <id>` → queues one pending file, silent.
- `sweep.py --dry-run` → prints a dict containing `'flagged': N`.
- `sweep.py` (no flag) → writes `.last-sweep` with today's date.
