# Changelog

All notable changes to AETHER OS are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[SemVer](https://semver.org/).

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
