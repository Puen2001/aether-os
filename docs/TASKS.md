# Task pattern — master backlog + daily slates

Two-tier task system across vaults. One file is the backlog of record; the
per-vault `tasks.md` files become small, curated daily slates instead of
ever-growing lists.

## The two tiers

**`tasks-master.md`** (repo root) — the cross-vault backlog of record.
- Grouped by project, priority-ranked (`#P1` highest).
- Each card may carry an indented description: context, links, acceptance.
- This is the only place descriptions live.

**`vaults/<vault>/tasks.md`** — a daily slate, not a backlog.
- Curated from master at the start of the day.
- Default discipline: at most one task per active project per day, a handful
  of cards per vault. Small slates get finished; long lists rot.
- Cards are title-only: `- [ ] <project> — <task> #P<n>`. No indented
  descriptions, no HTML — kanban plugins render titles only and mangle the
  rest. If you need the context, follow the card back to master.

## States

- `- [ ]` pending, `- [/]` doing, `- [x]` done (same as core).
- `BLOCKED` prefix in master: upstream dependency unmet — skip when curating.
- `PENDING` prefix in master: deliberately deferred by you — resurfaces at
  the end of curation, not silently dropped.

## Lifecycle

1. New work lands in `tasks-master.md` under its project, with priority.
2. Each morning (or session start) curate the day's slate per vault.
3. Work the slate; mark `[x]` as you go.
4. Completion deletes the card from master. No archive — `wiki/log.md` and
   git history are the record. A backlog that only grows is a graveyard.
