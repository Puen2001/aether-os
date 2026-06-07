# vault3 — domain vault

> A **domain vault** — one area of your life or work (e.g. personal, a project, a job).
> Assign its real meaning and rename it in `introduction.md`. See `system/SYSTEM.md` for doctrine.

## Three-layer shape

- `raw/` — your input: notes, pasted material, exports, transcripts. Unfiltered.
- `wiki/` — the assistant's synthesis: durable pages built from `raw/`, with an
  `index.md` catalogue and an append-only `log.md`.

## Rules

- The assistant **reads across** all vaults but **writes only within** this vault when run from here.
- Domain-specific or sensitive content stays here — it does NOT move to the shared-knowledge
  vault unless rewritten generically and passed through the IP-clean placement check
  (`system/SYSTEM.md` §3).
- Keep `wiki/index.md` current; append one line to `wiki/log.md` on every ingest.
