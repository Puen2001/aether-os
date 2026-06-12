# Layered architecture

The shape this scaffold converges on once voice, memory, and multiple vaults
are all live: three layers plus a feedback loop, with the harness underneath.

## Layers

**1. Control** — the session you open at the repo root.
Strategy, governance, cross-vault synthesis, and triage. Raw inputs
(notes, inbox captures, raw voice transcripts) are allowed to be messy here;
they are staging, not knowledge — they get filtered before they land anywhere
that is shared.

**2. Core — filters and routing** (the shared-knowledge vault + `system/`).
Everything that decides what goes where:
- The placement test on every page: "if I left this job / sold this venture,
  would this note have to be deleted?" Yes → it stays in its domain vault.
  No → it is eligible for the shared-knowledge vault, marked `ip_clean: true`.
- Memory governance (confidence, expiry, sweeps) deciding what the assistant
  is allowed to keep believing.
- The doctrine library (`concepts/`, `entities/`, `analysis/`) — portable
  technique, citable across every vault.

**3. Vaults — execution.** Bounded domains (work, personal, ventures), each
with its own `CLAUDE.md`, its own wiki, its own daily slate. Sessions opened
in a vault write only to that vault; the cwd is the permission boundary.

## The feedback loop

What keeps the layers honest is the upward flow:

- voice transcripts → daily digests → next session's context
- task completions → deleted from the master backlog, logged in `wiki/log.md`
- every prompt/dispatch → hashed event log → `tools/dispatch-report`
- every new page → `wiki/index.md` + `wiki/log.md`

Observations made at the bottom (execution) climb back to the top (control)
without manual copying. If the loop is broken anywhere, the system silently
degrades into disconnected folders.

## The harness

Hooks, launchers, and config (`.claude/settings.json`, `system/hooks/`,
`tools/`) sit under all three layers. Rule of thumb: the harness automates
*plumbing* (sync, digests, logging, nudges) and never automates *judgment*
(what to keep, what to delete, what is clean to share) — judgment stays in
sessions where you can see it.
