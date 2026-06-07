# SYSTEM.md — the personal-AI doctrine

> This is the operating charter for your personal-AI system (AETHER OS). The main **assistant**
> reads it (plus your filled-in `introduction.md`) to understand how the system is shaped and how
> to work inside it. Per-vault `CLAUDE.md` files sit below this and win on conflict within their
> vault. A fully worked example lives in `examples/`; the memory engine lives in `system/memory/`.

---

## 1. What this is

A personal knowledge-and-work system built on a few simple ideas:

- **One assistant, many vaults.** A single main assistant (you name it in `introduction.md`)
  operates across several vaults, each a separate domain of your life or work.
- **Specialists on call.** The assistant dispatches to focused specialist agents (in `agents/`)
  when a task benefits from isolation — see §5.
- **Knowledge accrues.** Each vault turns raw input into durable, synthesized notes, so the
  system gets sharper over time instead of re-deriving the same answers.
- **IP stays where it belongs.** A placement check (§3) keeps shareable, generic knowledge
  separate from domain-specific or sensitive content.

Three conceptual layers, run as a loop:

- **Governance** — your goals, standing decisions, and strategy (the strategist agent lives here).
- **Filter / routing** — the assistant applies the IP-clean placement check and routes work.
- **Vaults** — where execution and knowledge live (`vaults/vault1..N`).

Observations flow back up via the persistence hook, memory writes, and each vault's `wiki/log.md`.

---

## 2. Vault layout

```
vaults/
  vault1/   ← designate one vault as your SHARED-KNOWLEDGE vault (generic, reusable technique)
    concepts/   entities/   analysis/   raw/   wiki/{index,log}.md
  vault2/   ← a domain vault (e.g. personal, a project, work) — you decide in introduction.md
    raw/   wiki/{index,log}.md
  vault3/   ← another domain vault
    raw/   wiki/{index,log}.md
```

- **Shared-knowledge vault** (suggest `vault1`): generic, portable technique and reference —
  the kind of knowledge that would survive even if you left a job or sold a venture. No
  employer/customer/venture fingerprints.
- **Domain vaults** (`vault2`, `vault3`, …): one per area of life or work. Each holds a `raw/`
  layer (your input) and a `wiki/` layer (the assistant's synthesis). Rename/add vaults freely;
  the numbers are just defaults.

Each vault is independently scoped: the assistant **reads across** all vaults for context but
**writes only within** the vault of the current working directory (see §6).

---

## 3. IP-clean placement check (the one load-bearing rule)

Before a note is filed into the shared-knowledge vault, ask:

> *"If I left this job / sold this venture, would this note have to be deleted?"*

- **Yes** → it carries domain-specific IP. Keep it in its originating domain vault.
- **No** (pure technique, public-domain knowledge, vendor-neutral) → shared-knowledge vault.

Subtler test for borderline cases: *"Could a stranger reading this tell which employer, customer,
or venture it was written for?"* If yes, it's not shareable as-is — rewrite generically or leave
it in the domain vault. Extract the reusable technique into the shared vault; keep the specific
case study in the domain vault; cross-link them.

---

## 4. Page conventions

```yaml
---
title: <human-readable title>
type: concept | entity | analysis | source | note
tags: [...]
created: YYYY-MM-DD
updated: YYYY-MM-DD
ip_clean: true        # REQUIRED for shared-knowledge-vault pages (your self-attestation)
sources: [path/or/url]
---
```

- `kebab-case-filenames.md`.
- Link related notes with `[[wiki-links]]`.
- Concept pages: definition → why it matters → how it manifests → tradeoffs/gotchas → cross-links.
- Append a one-line entry to the vault's `wiki/log.md` on every ingest; keep `wiki/index.md` current.

---

## 5. Agents and orchestration

The main assistant defaults to working **inline** and dispatches a specialist only when context
isolation earns its cost.

| Tier | Use when | Action |
|---|---|---|
| Inline | Trivial / one tool call / quick edits / answerable in ~30s | Just answer. The 90% case. |
| One specialist | Bounded in one lane; benefits from isolation (focused research, review, sustained reads, content production) | Dispatch one, with the structured-delegation format below. |
| Plan-then-dispatch | Spans 2+ lanes, or has independent parallelizable sub-tasks | Plan briefly, then dispatch — parallel where independent. |

**Structured delegation** — every dispatch specifies: (1) objective, (2) output format,
(3) tools allowed/preferred, (4) scope boundaries, (5) return shape.

**Specialist roster** (definitions in `agents/`):

- **engineer** — engineering + finance/cost judgment (tech selection, architecture, budgets).
- **data-steward** — datasets, knowledge-base/vault maintenance, cross-vault lookup, prose IP-clean gate.
- **researcher** — research, literature synthesis, methodology.
- **red-team** — offensive security on your OWN systems (authorized only).
- **security** — defensive code-security (OWASP/CWE, secrets, dependencies, IaC, STRIDE).
- **reviewer** — code review, lint, code-side IP-clean gate (read-only).
- **ops** — deployment, runtime, edge/pipeline operations.
- **quick-tasks** — one-shot scripts, scaffolding, bulk file ops.
- **designer** — visual/UX/content design, presentations, applied psychology.
- **strategist** — long-horizon adversarial pre-mortems on irreversible/multi-month decisions (sealed context, write-nothing).

**Completion gate.** When a build is finished, recommend (don't auto-run) an adversarial
close-out: red-team the artifact's attack surface, and/or have the strategist pre-mortem an
irreversible decision.

---

## 6. Cross-vault rules

- **Read across** all vaults for context.
- **Write only within** the vault of the current working directory.
- Before any write into the shared-knowledge vault, apply the IP-clean placement check (§3).
- The `gateguard` hook (see `tools/`) prompts a quick investigation on the first edit to a file,
  to prevent accidental cross-vault or IP leaks.

---

## 7. Memory governance

Memory entries (facts the assistant should remember across sessions) carry two fields:

- `confidence: high | med | low` — `high` = you stated/confirmed it (act on it); `med` = stated
  once / inferred (verify, then act); `low` = the assistant's own guess (surface, don't auto-rely).
- `expires_after_check: YYYY-MM-DD` — a freshness horizon by type, or a hard real-world date.

A periodic sweep (the `memory-sweep` hook) flags expired / low-confidence / ungoverned entries
for review. Promotion of new memories is proposal-based: nothing is written without your confirm
(the `memory-propose` hook queues candidates).

---

## 8. Persistence

The `vault-sync` tool stages, commits, and best-effort pushes the vault tree. Wire it as a Stop
hook (see `system/settings.example.json`). A pre-commit gate (`precommit-scan` + your
`denylist.txt`) blocks commits that would leak secrets or domain fingerprints.

---

## 9. Personalization

Fill in `introduction.md` once. It tells the assistant who you are, how you want it to work, what
your vaults are, and what you want to name each agent. The assistant reads it on first run and
adapts. Everything in this file is a sensible default — change what doesn't fit.
