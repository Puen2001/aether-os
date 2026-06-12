```
       █████╗ ███████╗████████╗██╗  ██╗███████╗██████╗      ██████╗ ███████╗
      ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔════╝██╔══██╗    ██╔═══██╗██╔════╝
      ███████║█████╗     ██║   ███████║█████╗  ██████╔╝    ██║   ██║███████╗
      ██╔══██║██╔══╝     ██║   ██╔══██║██╔══╝  ██╔══██╗    ██║   ██║╚════██║
      ██║  ██║███████╗   ██║   ██║  ██║███████╗██║  ██║    ╚██████╔╝███████║
      ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝     ╚═════╝ ╚══════╝
   ──────────────────────────────────────────────────────────────────────────
            the personal AI that remembers you — and keeps your worlds apart
                       one assistant · many vaults · no bleed
```

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Free forever" src="https://img.shields.io/badge/free-forever-brightgreen">
  <img alt="No telemetry" src="https://img.shields.io/badge/telemetry-none-success">
  <img alt="Runs on Claude Code or any LLM" src="https://img.shields.io/badge/runs%20on-Claude%20Code%20or%20any%20LLM-5A4FCF">
  <img alt="Setup: one command" src="https://img.shields.io/badge/setup-one%20command-orange">
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-ff69b4"></a>
</p>

# AETHER OS

**The personal AI that remembers you — and keeps your worlds apart.**

AETHER OS gives your AI assistant a careful, *governed* memory of who you are — and a
built-in **IP-clean filter** so your personal, employer, and client worlds never bleed into each
other. One assistant. Many vaults. No bleed. **Runs fully local on your own model** — or any cloud
LLM you choose. **MIT-licensed. Free forever.**

```bash
git clone https://github.com/Puen2001/aether-os && cd aether-os && claude
```

Then say: **"Read examples/introduction.md and introduce yourself."** That's the whole taste — no
wiring, nothing written, nothing leaves your machine.

---

## Your code never leaves your machine

The exact worry behind *"is there an AI that won't ship my company's code to the cloud?"* — AETHER
is built for it:

- **Local-first brain.** Point it at a free local model (Ollama / LM Studio) and **nothing goes to
  any cloud AI** — your prompts, code, and notes stay on your machine. Cloud providers (Claude Code,
  OpenAI, Gemini, …) are opt-in, one per command — you choose, per command, what (if anything) leaves.
- **Scoped access, not your whole disk.** It writes only inside the vault you're working in, and the
  voice assistant reads only the vaults you whitelist (`READ_VAULTS`) — the model never sees more
  than you scope to the question.
- **A leak gate before anything ships.** A pre-commit scan blocks secrets and client/company
  fingerprints from landing in notes you'd share.

No tool is 100% safe — but this removes the "I pasted company code into a cloud AI" risk by default.
*(ไม่การันตี 100% แต่ตัดความเสี่ยงโค้ดบริษัทรั่วเข้า cloud AI โดยตรงออกไปได้ตั้งแต่ต้น)*

---

## The 60-second aha

Raw ChatGPT/Claude forgets you between sessions and treats your day job, your side venture, and
your client work as one undifferentiated blob — fine until the day a client detail lands in a note
you'd ship to your employer.

AETHER fixes exactly that:

- **It remembers you — carefully.** Every fact carries a *confidence* and an *expiry*, and new
  memories are **proposed for your confirmation, never written silently**. A periodic sweep retires
  stale ones. Memory you can audit, not a black box.
- **It keeps your worlds apart.** Personal, employer, and client knowledge live in separate
  **vaults**. Before anything is filed as shareable, AETHER asks one question:

  > *"If I left this job or sold this venture, would this note have to be deleted?"*

  Yes → it stays walled in its domain vault. No → portable, shareable technique. A pre-commit gate
  **catches** a client name or secret before it slips into your public notes.

> **What the first run looks like** *(animated demo coming soon)*
> 1. `git clone … && cd aether-os && claude`
> 2. *"Read examples/introduction.md and introduce yourself."*
> 3. The assistant introduces itself as the worked persona's AI, reads back what it learned —
>    then files two notes on **opposite sides of the wall**: a reusable technique into the shared
>    vault, a client-specific detail into the walled client vault. Same work, sorted by world.

Every other AI second brain gives you one memory blob. **Only AETHER walls your worlds off** — the
thing that makes an AI second brain safe to use for work you don't own.

---

## Why this exists

I built AETHER OS to fix my own pain: an AI that forgets me every session, is locked inside one
vendor, blends my separate worlds together, and lives on someone else's servers. I wanted my **own
private AI ecosystem** — one that knows me, keeps my contexts clean, runs as files I own, and that I
can reach from anywhere. This is the free, open version of that. If the pain is yours too, it's yours.

---

## Why not just ChatGPT / Notion AI / another second brain?

*(capability comparison as of 2026-06; these tools evolve — corrections welcome)*

| | **AETHER OS** | ChatGPT / Claude (raw) | Notion AI / Smart Connections | Other second-brains-on-Claude |
|---|:---:|:---:|:---:|:---:|
| **Structural per-vault isolation, enforced at commit** | ✅ | ❌ | ❌ | ⚠️ rarely |
| **Memory you confirm + audit** (confidence + expiry, proposed not silent) | ✅ | ⚠️ opaque | ⚠️ | ⚠️ |
| **Pre-commit gate that catches secret / client-name leaks** | ✅ | ❌ | ❌ | ❌ |
| Plain Markdown you own, no lock-in | ✅ | ❌ | ❌ | ✅ |
| 11 role agents + ~16 skill packs included | ✅ | ❌ | ❌ | ⚠️ varies |
| No telemetry — hashed local logs only | ✅ | ❌ | ❌ | ⚠️ |
| Free, MIT, complete (not a crippled demo) | ✅ | n/a | ❌ | ✅ |

The first row is the one nobody else has.

---

## What's in the box

```
aether-os/
  aether              <- one command: init / doctor / reset / sync
  introduction.md     <- the one file you fill in (blank template)
  agents/             <- the assistant + 10 specialists (role-named; rename freely)
  skills/             <- ~16 auto-triggering methodology packs
  tools/              <- the wiring: hashed logging, memory loop, sync, pre-commit gate
  system/             <- SYSTEM.md doctrine + settings template + memory engine + git hooks
  vaults/             <- shared-knowledge vault + two domain vaults
  examples/           <- a fully worked persona you can read, then delete
```

- **11 agents** — a main assistant (the one you talk to) + engineer, data-steward, researcher,
  red-team, security, reviewer, ops, quick-tasks, designer, strategist. They ship **role-named under
  the one AETHER OS brand — you give them whatever names you like** in `introduction.md`. Dispatched
  only when isolation earns its cost.
- **~16 skill packs** — vendor-neutral methodology (API design, CI/CD, a deep security audit, ML
  workflow, performance, docs/ADRs, context-engineering…) that auto-trigger by description.
- **The wiring** — sha256-hashed event logging, a governed-memory loop, opt-in vault sync, a
  pre-commit secret + IP-fingerprint gate.
- **A worked example, pre-loaded** — a fictional persona, two vault notes, and memory entries under
  `examples/`, all marked **"delete to start fresh."**

---

## Quickstart

**Claude Code is not required — it just unlocks the most.** Mix and match:

- **With Claude Code** — the full experience. You get the 11 agents, skills, and
  lifecycle hooks (these use Claude Code's own formats), on top of everything
  below. Zero extra model calls — your only spend is your normal Claude Code usage.
- **With any other AI** — Codex, Gemini, OpenAI, a free local model (Ollama,
  LM Studio), or any chat CLI. AETHER still runs, with a smaller feature set: the
  voice/phone assistant, your vaults, the knowledge base, and the tools all work.
  The Claude-Code-only parts — the agents, skills, and hook automation — stay off.
  See [Voice & any-backend setup](#voice--any-backend-setup).

macOS, Linux, or **Windows via WSL2**.

### 30-second taste (no setup, no risk)
```bash
git clone https://github.com/Puen2001/aether-os && cd aether-os && claude
```
In the assistant: **"Read examples/introduction.md and introduce yourself."**
You'll see the first-run experience against a filled-in persona. (This taste runs with hooks **off** —
nothing is written, nothing leaves your machine. `./aether init` turns on the memory + gate.)

> **No Claude Code?** Skip the taste above and jump to
> [Voice & any-backend setup](#voice--any-backend-setup) — talk to AETHER over a
> local Ollama model instead.

### Make it yours
```bash
./aether init        # copies templates, sets exec bits, wires the pre-commit gate — ~5s, idempotent
./aether intro       # opens introduction.md in your editor — name yourself + your assistant
```
`./aether intro` is where you personalize: set **"Name / what to call you"** and how you want your
assistant to work. Then open the assistant **from this folder** (`claude`, or `./voice/voice.sh` for
any backend) — it reads `introduction.md` on first run. Run `./aether doctor` any time to check your
setup; `./aether reset` clears the example.

### Your own commands (one per AI)

`aether` is the default command, but you can make your own — handy if you use more than one AI and
want a separate command for each (like `myai-local`, `myai-gpt`, `myai-claude`):

```bash
./aether launcher            # asks a name + which backend, writes launchers/<name>,
                             # offers to put it on your PATH, then asks if you want another
```

Each generated command opens a terminal chat on its backend (Claude Code, a local Ollama model, a
hosted API, or any chat CLI), personalized from your `introduction.md`. They're plain scripts under
`launchers/` — edit them freely.

### Voice & any-backend setup

Talk to AETHER with no Claude Code at all. Point the brain at a free local model:

```bash
# 1. a brain backend — free + local via Ollama (or any OpenAI-compatible API)
ollama pull llama3.1

# 2. speech-to-text
brew install whisper-cpp        # or build https://github.com/ggml-org/whisper.cpp

# 3. configure + run
cp voice/config.env.example voice/config.env   # defaults to local Ollama + the `say` voice
./voice/voice.sh                                # press Enter to talk
```

Other backends (set `BRAIN_PROVIDER` in `voice/config.env`): a hosted API
(`api` + `BRAIN_API_KEY` in `~/.config/personal-ai/voice/secrets.env`), any chat
CLI (`cmd`), or the Claude Code / Codex CLI. Phone access via
`voice/telegram-bridge.py`. Details in
[`system/brain/README.md`](system/brain/README.md).

### Windows
Install [WSL2](https://aka.ms/wsl), then run the steps above inside your WSL2 Linux home (not a
native PowerShell/Git-Bash shell — the hooks need a real shell). `./aether doctor` will confirm.

---

## How it works (short version)

- **One assistant, many vaults.** It reads *across* all your vaults for context but writes
  *only within* the vault you're working in.
- **Knowledge accrues.** Each vault turns raw input into durable, synthesized notes — the system
  gets sharper instead of re-deriving the same answers.
- **IP stays where it belongs.** The placement check keeps shareable technique apart from sensitive,
  domain-specific content — backed by a pre-commit gate.
- **It remembers, carefully.** Memory carries confidence + expiry; new memories are proposed, never
  written silently; a sweep flags stale ones.

Full charter: [`system/SYSTEM.md`](system/SYSTEM.md).

---

## The 11 agents

| Role | What it does |
|---|---|
| **assistant** | Your main AI — the orchestrator you talk to |
| **engineer** | Engineering + finance/cost judgment |
| **data-steward** | Datasets, knowledge base, vault upkeep, lookups |
| **researcher** | Research, literature synthesis, methodology |
| **red-team** | Offensive security on your own systems (authorized only) |
| **security** | Defensive code security (secrets, dependencies, OWASP/CWE, STRIDE) |
| **reviewer** | Code review and lint (read-only) |
| **ops** | Deployment, runtime, operations |
| **quick-tasks** | Quick scripts, scaffolding, bulk file ops |
| **designer** | Visual / UX / content design, presentations |
| **strategist** | Adversarial pre-mortems on big, hard-to-reverse decisions |

No fixed names — everything is AETHER OS, and you name the agents yourself in
[`introduction.md`](introduction.md). Roster defined in [`system/SYSTEM.md`](system/SYSTEM.md) §5.

---

## Privacy & security

AETHER OS is built to be safe to use for work you don't own.

- **No telemetry, ever.** Nothing phones home. The event log **sha256-hashes your input** instead of
  storing prompts in plaintext (`tools/dispatch-trace.py`).
- **No network egress by default.** Vault sync commits *locally only* until you opt in with your own
  git remote — a fresh clone can never push upstream.
- **Secrets + client names are gitignored and gated.** `tools/*.env` and `system/denylist.txt` are
  gitignored; `tools/precommit-scan` blocks a commit that would leak a secret key or a denylisted name.
- **The IP-clean gate is a control you can point to** — defense-in-depth enforced at commit time, not
  a guarantee that a leak is impossible.
- **Fail-loud, never fail-silent.** `./aether doctor` makes a half-wired setup visible; the edit-gate
  hook has a kill switch (`GATEGUARD=off`) and never blocks on its own bug.

Per-tool data-flow detail: [`docs/PRIVACY.md`](docs/PRIVACY.md). Report a vulnerability:
[`SECURITY.md`](SECURITY.md). This repo ships **no personal data** — the only filled-in content lives
in `examples/`, clearly marked for deletion.

---

## Roadmap

AETHER OS works today. Where it's going:

- **Any medium, one core.** AETHER is a personal AI *core* with pluggable front-ends — voice,
  messaging bridges (Telegram/Discord), mobile, desktop, web. Reach the same memory and vaults from
  anywhere. (A Telegram bridge stub already ships in `tools/`.)
- **Local-LLM mode.** Run AETHER fully on local/open models — offline-capable, provider-independent.
- **Domain packs.** Drop-in role + vault bundles for a life domain — a personal trainer / health
  coach, a finance coach, a study tutor.

Full detail: [`ROADMAP.md`](ROADMAP.md).

---

## Free forever — and what "Pro" would add

**AETHER OS is MIT-licensed and free forever. The entire scaffold on this page is the product, not a
teaser.** Every agent, every skill, the memory governance, the IP-clean filter, the opt-in sync — all
of it runs for life without paying anyone, including for commercial and client work.

A future **AETHER Cloud / Pro** is for people who'd rather not run their own harness — *managed
convenience on top, never a wall around the basics:* hosted setup + a guided wizard, **automated**
multi-agent orchestration and a deep-research engine (the free tier ships the agents; you dispatch
them yourself — Pro automates the orchestration), managed multi-machine sync, client-showable
audit/attestation artifacts, an air-gapped local-LLM mode, voice + mobile bridges, and premium skill
+ domain packs.

Want it, or have feedback? **[Watch this repo ⭐](https://github.com/Puen2001/aether-os) ·
[say so in Discussions](https://github.com/Puen2001/aether-os/discussions)** — no countdowns, no nags.

---

## Contributing

Issues and PRs welcome — new vendor-neutral skill packs, `./aether doctor` checks, and worked-example
personas for other professions most of all. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and the
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © 2026 the AETHER OS contributors. Use it, fork it, sell what you build with it.

AETHER OS is an independent open-source project and is **not affiliated with, endorsed by, or
sponsored by** Anthropic, xAI, or any other company; product/company names are their owners' marks.
Lineage: the personal-AI-infrastructure pattern owes a debt to
[Daniel Miessler's PAI](https://github.com/danielmiessler/Personal_AI_Infrastructure) and Andrej
Karpathy's LLM-wiki idea. AETHER's contribution is **governed memory plus governed boundaries**.
