# tools/

Reusable infrastructure scripts for a personal-AI vault. Every script here is
self-contained, stdlib/POSIX-only, and resolves paths against `$HOME`,
`$CLAUDE_CONFIG_DIR`, `$VAULT_ROOT`, or its own location — no absolute personal
paths are baked in.

## Tool index

| Tool | Purpose | Needs config? |
|---|---|---|
| `dispatch-trace.py` | Append-only event logger. Logs prompt/dispatch/turn-end events with all user text sha256-hashed (privacy-preserving). Writes JSONL to `$CLAUDE_CONFIG_DIR/logs/dispatch.jsonl` (falls back to `~/.config/personal-ai/logs/`). | No |
| `gateguard.py` | PreToolUse(Edit\|Write) fact-forcing gate. Denies the first edit to a file per session and demands the assistant investigate (grep callers, quote the instruction, run the placement test); the retry passes. Kill switch: `GATEGUARD=off`. Optional `GATEGUARD_VAULT_MARKER` to set the vault path fragment. | Optional env |
| `precommit-scan` | Secret/IP pre-commit gate. Scans staged added lines for secret-key patterns (repo-wide) and the user denylist (shareable vault zones only). Exit 1 on a hit. | Reads `system/denylist.txt` (optional) |
| `precommit-patterns.txt` | Universal secret-key egrep patterns used by `precommit-scan`. Committed, public-safe. | No |
| `vault-sync` | Best-effort git auto-persist: stage all -> secret/IP gate -> commit -> detached push. **Auto-push is OPT-IN** (off by default; commits locally only until you enable it). Lock-protected. Resolves the repo via `$VAULT_ROOT` (defaults to one level up from `tools/`). | Push needs opt-in: `tools/setup-git.sh` or `VAULT_AUTOPUSH=1` |
| `setup-git.sh` | One-time, opt-in: start a fresh git history, point `origin` at YOUR repo, initial commit + push, and enable auto-push. `tools/setup-git.sh <your-remote-url> [--no-autopush]`. Disable later with `rm tools/.autopush-enabled`. | Your own git remote URL |
| `memory-sweep-due.sh` | SessionStart nudge when the memory-governance sweep is >=90 days overdue. Read-only, silent on the happy path. Expects `system/memory/sweep.py`. | Needs `system/memory/sweep.py` |
| `memory-propose.sh` | SessionEnd hook. Queues the ended session for the next start's memory-review pass. No model call. Expects `system/memory/propose.py`. | Needs `system/memory/propose.py` |
| `memory-proposals-resume.sh` | SessionStart nudge listing sessions that ended without a memory-review pass. Expects `system/memory/propose.py`. | Needs `system/memory/propose.py` |
| `statusline.py` | Compact Claude Code status line: model, context bar, dir, git branch+dirty, rate limits, cost, elapsed. Segments auto-omit when data is absent. | No |
| `telegram-send` | Fire-and-forget Telegram notifier for out-of-band pings. Degrades gracefully (prints a notice, exits non-zero) if unconfigured. | `telegram.env` (copy from `telegram.env.example`) |
| `telegram.env.example` | Placeholder Telegram credentials. Copy to `telegram.env` and gitignore it. | — |

The three `memory-*` hooks call a reference memory engine that **ships with AETHER OS**
(`system/memory/propose.py` + `sweep.py` — see `system/memory/README.md`); extend it to taste.
`vault-sync` is opt-in: with no git `origin` remote / opt-in flag it commits locally only.
All of these fail open — if a target script or remote is absent they exit cleanly and do nothing.

## Hook wiring

`system/settings.example.json` is a clean Claude Code settings template. It wires:

| Event | Script | What it does |
|---|---|---|
| SessionStart | `memory-proposals-resume.sh`, `memory-sweep-due.sh` | Surface pending memory reviews / overdue sweep |
| SessionEnd | `memory-propose.sh` | Queue the session for next-start memory review |
| PreToolUse(Edit\|Write) | `gateguard.py` | Force investigation before first edit per file |
| UserPromptSubmit | `dispatch-trace.py` | Log a hashed prompt event |
| PostToolUse(Agent) | `dispatch-trace.py` | Log a hashed dispatch event |
| Stop | `dispatch-trace.py`, `vault-sync.sh` | Log turn-end + commit the vault (push only if you opted in via `setup-git.sh`) |
| statusLine | `tools/statusline.py` | Render the compact status line |

The settings template points at `system/hooks/<name>`, which are thin forwarders
to the canonical implementations in `tools/`. This keeps one source of truth
(edit `tools/`) while letting hooks live under `system/hooks/`. If you prefer,
repoint the settings commands directly at `tools/<name>` — both work.

Hook commands are written as repo-relative paths; Claude Code runs them with the
project root as the working directory. If you need absolute paths, prefix with
`${CLAUDE_CONFIG_DIR}/` or your vault root.

## Activating

**The one-command path:** from the repo root, run `./aether init` — it does steps 1–4 below
(copy templates, set exec bits, wire the gate, seed the denylist) in one idempotent pass, then
`./aether doctor` verifies it. The manual steps are kept here for reference / customization.

1. Copy the settings template to your live settings and adjust paths if needed:

   ```bash
   cp system/settings.example.json .claude/settings.json
   # or point Claude Code at this dir via CLAUDE_CONFIG_DIR
   ```

2. Make the scripts executable (if not already):

   ```bash
   chmod +x tools/*.py tools/*.sh tools/precommit-scan tools/vault-sync tools/telegram-send \
            system/hooks/* system/githooks/pre-commit
   ```

3. Enable the manual-commit secret gate:

   ```bash
   git config core.hooksPath system/githooks
   ```

4. (Optional) Set up the user denylist and Telegram:

   ```bash
   cp system/denylist.example.txt system/denylist.txt   # then gitignore it
   cp tools/telegram.env.example tools/telegram.env      # then gitignore it
   ```

5. (Optional) Back up to your own git with auto-push:

   ```bash
   tools/setup-git.sh https://github.com/you/your-vault.git
   # add --no-autopush to back up but push manually
   ```
