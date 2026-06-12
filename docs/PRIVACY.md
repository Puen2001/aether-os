# Privacy — how AETHER OS handles your data

AETHER OS is built to be safe to use for work you don't own.

**The short version:** by default — a local model brain, local text-to-speech,
no sync — **nothing you type, no code, and no note leaves your machine.** There
is no telemetry; nothing is ever sent to the project maintainers. The only ways
your content goes off-machine are integrations **you turn on yourself**, each
listed below.

You are the **sole data controller** for everything in your vaults. You remain
responsible for any data-protection obligations (GDPR / PDPA / NDA, etc.). The
IP-clean gate and local-first defaults are safeguards, **not a legal guarantee**,
and no setup is 100% leak-proof.

## What can send data off your machine — and when

Everything here is **off by default** or **only fires once you configure it**.
On a fresh clone with the shipped defaults, none of it sends your content out.

| Path | When it sends, and to whom | Your content leaves? |
|---|---|---|
| **Brain backend — local** (`BRAIN_PROVIDER=api` → Ollama / LM Studio, the shipped default; or `cmd` → a local model) | Stays on `localhost`. The model runs on your machine. | **No** |
| **Brain backend — hosted** (`api` pointed at OpenAI/OpenRouter/Gemini/…, or `claude` / `codex`) | Your prompt **and** whatever vault context the turn pulls in go to that provider, under **their** terms. This is the one to think about for company code. | **Yes — to the provider you chose** |
| **Telegram bridge** (`voice/telegram-bridge.py`, only if you add a bot token) | Your voice/text turns and the replies pass through Telegram's servers. | Yes — to Telegram, if enabled |
| **ElevenLabs TTS** (`TTS_PROVIDER=elevenlabs`, only with a key) | The **reply text** is sent to ElevenLabs to synthesize speech. Use `kokoro` (local) or `say` to keep it on-machine. | Yes — to ElevenLabs, if enabled |
| **KB embedding model** (`system/kb/build_kb.py`, first run) | Downloads the open embedding model from its host **once**; thereafter fully local. Your vault text is embedded **locally** and **never uploaded**. | Model download only — **not your data** |
| **`worldmap` toy** (`tools/eyecandy/worldmap`) | Fetches **public** feeds (USGS / GDELT / ISS / GDACS). Sends no personal data. `WORLDMAP_OFFLINE=1` disables it. | Public reads only — not your data |
| **Vault sync** (`./aether sync` / `setup-git.sh`) | Pushes your repo to **your own** git remote — opt-in, never automatic. | Only to **your** remote, after opt-in |

## Tools that stay fully local (no network, ever)

| Tool | What it does |
|---|---|
| `tools/dispatch-trace.py` | Appends a local log line storing a **SHA-256 hash** of your input, not the plaintext |
| `tools/precommit-scan` | Reads staged changes locally to flag common secret formats (vendor API keys, tokens, JWTs, connection-string creds) + your denylisted strings. A safety net, not a guarantee — review what you commit. |
| `tools/gateguard.py` | Prompts an investigation on the first edit to a file in a session |
| `tools/statusline.py` | Renders the status line from local git/context state |
| `system/memory/propose.py` · `sweep.py` | Record / scan local memory entries |
| `system/brain/chat.py` · `voice/voice.sh` | Drive whichever brain you configured — they add no network of their own |

## Verify it yourself (don't take our word)

This is open source and the audience is technical — so confirm it:

1. **Pick the local brain** (the default): `BRAIN_PROVIDER=api`,
   `BRAIN_API_BASE=http://localhost:11434/v1` (Ollama), local TTS (`kokoro` or
   `say`), and don't configure Telegram/ElevenLabs/sync.
2. **Watch the network** while you use it. On macOS:
   `sudo lsof -i -nP | grep -i python` (or Little Snitch / `nettop`); on Linux:
   `ss -tnp` or `sudo tcpdump -i any`. You should see traffic only to
   `127.0.0.1`/`localhost` (your Ollama), and nothing else.
3. **Grep the code yourself:** `grep -rnE 'urllib|requests|socket|http' --include='*.py'`
   — every network call is in the paths listed in the table above, and each is
   gated on a backend/integration you turned on.

## Read / write scope (what the assistant can touch)

- **Write scope is the configured CLI sandbox.** With defaults, the Claude
  backend is given read-only tools (`Read/Glob/Grep`) and Codex runs
  `--sandbox read-only`, so the assistant answers but does not edit. Setting
  `BRAIN_CODEX_SANDBOX=workspace-write` (or adding Write to allowed-tools)
  widens that — that's your call, not a default.
- **Read scope is the workspace.** The voice/Telegram brain is launched with the
  repo root as its workspace plus your `READ_VAULTS` whitelist, so in the default
  layout it *can* read the other vaults in the tree even if they aren't
  whitelisted. For strict isolation of a private vault, keep it **outside** the
  workspace (point `VAULTS_DIR`/workspace at only the vault you want exposed).

## What is gitignored (never committed)

- `voice/config.env`, `voice/secrets.env`, `tools/*.env`, `system/denylist.txt`
  — your machine-local config and secrets; only `*.example` templates are tracked.
- `system/voice/.transcripts-raw/` (raw voice transcripts), `system/kb/lance/`
  (your local index), `launchers/` (your generated commands).
- `tools/.autopush-enabled`, logs, caches, and OS/editor cruft.

## On hashing

`dispatch-trace.py` stores a SHA-256 hash of input rather than the text. This
prevents *casual* recovery of your prompts from the log. It is **not**
cryptographic anonymization: short, low-entropy inputs could in principle be
brute-forced by someone who already has your local log file. The log never
leaves your machine, so this is defense-in-depth, not a guarantee against a
local attacker.

## Cost / model calls

The **harness** (hooks, memory engine, sync, gate) is deterministic shell/Python
and makes **no** model calls of its own. The only AI calls are the ones your
chosen brain makes: a **local** model costs nothing and sends nothing; a
**hosted** provider (Claude Code, OpenAI, …) bills and behaves under that
provider's own terms.
