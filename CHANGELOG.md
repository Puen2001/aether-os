# Changelog

All notable changes to AETHER OS are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[SemVer](https://semver.org/).

## [0.2.0] — 2026-06-12

### Added
- **Voice + phone interface.** Push-to-talk voice loop (`voice/voice.sh`):
  mic → Whisper (auto language) → brain router → TTS (local Kokoro / ElevenLabs
  / OS voice), with handsfree hold-key, wake word, barge-in, and a follow-up
  listening window. Telegram bridge (`voice/telegram-bridge.py`) for voice-note
  and text turns from a phone, sharing the desktop session.
- **Pluggable brain router** (`system/brain/router.py`). The voice/phone stack
  runs on **any** LLM backend, not just Claude Code:
  - `api` — any OpenAI-compatible endpoint: a free local model (Ollama,
    LM Studio, llama.cpp, vLLM) or a hosted API (OpenAI, OpenRouter, ...);
  - `cmd` — pipe each turn through any local chat CLI;
  - `claude` / `codex` — still supported, no longer required.
  Default config ships a fully local Ollama brain (zero network, no key).
- **Voice continuity hooks** — a Stop hook digests each day's voice transcript;
  a SessionStart hook surfaces recent spoken turns into new sessions
  (Claude Code only; non-Claude users can run the digester from cron).
- **Local knowledge index** (`system/kb/`) — offline LanceDB hybrid search over
  the shared-knowledge vault and voice digests; query with `recall.py`.
- **Vault tools** — `tools/vault-lint` (orphan / stale / missing-`ip_clean`
  pages) and `tools/dispatch-report` (analytics over the dispatch log).
- **Task pattern** — master backlog + daily slate workflow (`docs/TASKS.md` +
  `tasks-master.md`).
- **Cosmetics** — upgraded status line and a terminal eye-candy kit
  (`tools/eyecandy/`).
- **Onboarding + custom commands.** `./aether intro` opens `introduction.md`
  to name yourself and your assistant. `./aether launcher` generates your own
  named terminal command(s) — one per AI provider (e.g. `myai-local`,
  `myai-gpt`) — each opening a backend-agnostic text chat
  (`system/brain/chat.py`) personalized from `introduction.md`.

### Changed
- Quickstart reframed: **Claude Code is no longer required.** It remains the
  default agent runtime (zero extra cost), but the assistant/voice layer runs on
  any LLM backend. The agents, skills, and hooks still use Claude Code formats.

## [0.1.1] — 2026-06-07

### Added
- Memory engine: **deterministic short-window SHA-256 dedup** in `propose.py` — identical session
  content recorded within 10 minutes is queued once (no model call).
- Memory sweep: **duplicate-entry detection** (body content-hash) and **typed relationship edges**
  in entry frontmatter — `supersedes` (flags the superseded entry stale), `contradicts` (flags both
  for review), `extends` (informational). The `'flagged': N` hook contract is unchanged.

_(Ideas adapted clean-room from a tool-hunt of agentmemory; no code lifted.)_

## [0.1.0] — 2026-06-07

First public release — the free, MIT-licensed AETHER OS scaffold.

### Added
- One assistant + 10 role-named specialist agents (rename them yourself in `introduction.md`).
- ~16 vendor-neutral, auto-triggering skill packs.
- Governed memory engine: `system/memory/{propose,sweep}.py` (confidence + expiry,
  propose-don't-write-silently, a staleness sweep).
- The IP-clean placement check + a pre-commit secret/IP-fingerprint gate.
- `aether` one-command dispatcher (`init` / `doctor` / `reset` / `sync`).
- Opt-in vault sync (auto-push off by default; nothing leaves your machine until you say so).
- A fully worked example persona under `examples/` (delete to start fresh).
- MIT `LICENSE`, `NOTICE.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `docs/PRIVACY.md`.
