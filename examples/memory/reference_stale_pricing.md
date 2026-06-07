---
title: Cloud GPU spot price ballpark
type: reference
confidence: low
expires_after_check: 2026-04-01
created: 2026-01-15
source: a forum post (unverified)
---

> **EXAMPLE memory entry (fictional) — deliberately stale.** This one exists to show the
> **sweep catching something**: it is `confidence: low` AND its `expires_after_check` is in the
> past. Run `python3 system/memory/sweep.py --dry-run examples/memory` and watch it get flagged.
> Run `./aether reset` to start fresh.

A forum post claimed a certain spot GPU was "about $0.40/hr." Never confirmed, and prices move
monthly — exactly the kind of low-confidence, expiring fact the sweep should surface for
re-checking or deletion rather than letting it quietly rot in memory.
