# Privacy — how AETHER OS handles your data

AETHER OS is built to be safe to use for work you don't own. The short version:
**everything stays on your machine unless you explicitly opt in to syncing it to
your own git remote.** There is no telemetry and nothing is ever sent to the
project maintainers or any third party.

You are the **sole data controller** for everything you put in your vaults. AETHER
OS processes it entirely locally. You remain responsible for any data-protection
obligations (GDPR / PDPA / NDA, etc.) attaching to that data — the IP-clean gate is
a safeguard, not a legal guarantee.

## Per-tool data flow

| Tool | What it does with data | Leaves your machine? |
|---|---|---|
| `tools/dispatch-trace.py` | Appends an event line to a local log, storing a **SHA-256 hash** of your input, not the plaintext | No |
| `tools/vault-sync` | Stages + commits your vault locally; pushes **only** if you opted in via `./aether sync` / `setup-git.sh` | Only to **your own** remote, only after opt-in |
| `tools/precommit-scan` | Reads staged changes locally to block secrets / denylisted strings | No |
| `tools/gateguard.py` | Prompts an investigation on the first edit to a file in a session | No |
| `tools/telegram-send` | Sends a message **only if** you create and fill `tools/telegram.env` | Only if you configure it |
| `system/memory/propose.py` | Records a pending memory-review note from a session transcript, locally | No |
| `system/memory/sweep.py` | Scans your local memory entries for stale/low-confidence facts | No |

## On hashing

`dispatch-trace.py` stores a SHA-256 hash of input rather than the text. This
prevents *casual* recovery of your prompts from the log. It is **not** cryptographic
anonymization: short, low-entropy inputs (a name, a yes/no, a single command) could
in principle be brute-forced by someone who already has your local log file. The log
never leaves your machine, so this is a defense-in-depth measure, not a privacy
guarantee against a local attacker.

## What is gitignored (never committed)

- `tools/*.env` (your secrets) — only the `*.env.example` templates are tracked.
- `system/denylist.txt` (your private list of names that must never leak).
- `tools/.autopush-enabled`, logs, caches, and OS/editor cruft.

## The harness makes no extra model calls

The hooks are deterministic shell/Python — they do **not** call a model. Your only
AI spend is your normal Claude Code usage; AETHER OS adds none of its own.
