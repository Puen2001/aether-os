# Brain router

Shared text-in/text-out backend for the assistant's front-ends. The voice and
Telegram packs call this router instead of binding to one provider, so the same
stack runs on whatever brain you point it at.

```
front-end (voice / telegram-bridge)
    -> system/brain/router.py --prompt ... --persona ... [--resume <id>]
    -> the backend you configured (api / cmd / claude / codex)
    -> one JSON object on stdout
```

## Backends

Pick one with `--provider` (or the `BRAIN_PROVIDER` env var). None is required
to be installed -- configure whichever you have:

| Provider | What it calls | Needs |
|---|---|---|
| `api` | any OpenAI-compatible `/chat/completions` endpoint | a local server (Ollama, LM Studio, llama.cpp, vLLM) or a hosted API (OpenAI, OpenRouter, Together, Groq, ...) |
| `cmd` | an arbitrary local chat command, prompt on stdin | e.g. `ollama run llama3.1`, `llm -m ...`, any chat CLI |
| `claude` | the Claude Code CLI (headless, `Read/Glob/Grep` only) | Claude Code installed |
| `codex` | the Codex CLI (`--sandbox read-only`) | Codex installed |

`api` is the universal default and runs **fully local, free, and offline** when
pointed at Ollama or LM Studio. Example:

```bash
export BRAIN_PROVIDER=api
export BRAIN_API_BASE="http://localhost:11434/v1"   # Ollama
export BRAIN_MODEL="llama3.1"
# BRAIN_API_KEY only needed for a hosted endpoint
```

## Modes

`--mode` (or `BRAIN_MODE`) controls routing on top of the chosen provider:

| Mode | Behavior |
|---|---|
| `auto` | route to `BRAIN_PROVIDER`; if it is `claude`/`codex`, send code/debug/review-shaped prompts to Codex and the rest to Claude, with fallback to the other on failure |
| `api` / `cmd` / `claude` / `codex` | force that backend |
| `review` | force `codex review --uncommitted` |
| `both` | run Claude + Codex and return both views |

The Claude/Codex split in `auto` keeps the original behavior for Claude Code
users; with `BRAIN_PROVIDER=api` (or `cmd`) every prompt goes to that one
backend, which answers code and general prompts alike.

All backends are read-only assistants: Claude is restricted to `Read/Glob/Grep`,
Codex runs `--sandbox read-only`, and the `api`/`cmd` system prompt forbids
destructive claims. The voice surfaces read and answer; they do not edit.

## Configuration

Every flag has an env-var default:

| Flag | Env var | Default |
|---|---|---|
| `--provider` | `BRAIN_PROVIDER` | `claude` (the shipped `voice/config.env` overrides this to `api` → local Ollama) |
| `--mode` | `BRAIN_MODE` | `auto` |
| `--workspace` | `BRAIN_WORKSPACE` | repo root |
| `--timeout` | `BRAIN_TIMEOUT` | `150` (seconds) |
| `--api-base` | `BRAIN_API_BASE` | `https://api.openai.com/v1` |
| `--api-key` | `BRAIN_API_KEY` | unset (not needed for local servers) |
| `--api-model` | `BRAIN_MODEL` | `gpt-4o-mini` |
| `--cmd` | `BRAIN_CMD` | unset |
| `--claude-model` | `BRAIN_CLAUDE_MODEL` | CLI default |
| `--claude-config-dir` | `BRAIN_CLAUDE_CONFIG_DIR` | unset (standard Claude login store) |
| `--codex-model` | `BRAIN_CODEX_MODEL` | CLI default |
| `--codex-sandbox` | `BRAIN_CODEX_SANDBOX` | `read-only` |
| `--codex-persist` | `BRAIN_CODEX_PERSIST` | off (`1` to enable) |

The repo root is resolved from the script's own location and can be overridden
with `PAI_ROOT`. The voice packs expose the brain knobs in `voice/config.env`
and pass them through; `BRAIN_API_KEY` lives in `secrets.env`, not `config.env`.

## Smoke tests

Route only, no model call:

```bash
python3 system/brain/router.py --prompt "what is on my plate today" --dry-run
BRAIN_PROVIDER=api python3 system/brain/router.py --prompt "debug this error" --dry-run
```

A real call against a local Ollama:

```bash
BRAIN_PROVIDER=api BRAIN_API_BASE=http://localhost:11434/v1 BRAIN_MODEL=llama3.1 \
  python3 system/brain/router.py --prompt "say hello in one short sentence"
```

## Contract

The router prints one JSON object:

```json
{"type":"result","result":"...","session_id":"...","route":"auto","provider":"api"}
```

Callers only require `result` and `session_id`; `route`, `provider`, and the
per-backend `providers` array are for logs and future UI. `session_id` is
populated only by the `claude` backend (server-side session) and is what
front-ends persist to `~/.config/personal-ai/voice/.session` and feed back via
`--resume`. The `api`/`cmd`/`codex` backends are stateless, so `session_id`
stays empty there; cross-session continuity then comes from the voice-digest
hooks rather than provider-side resume. Exit code is 0 when a result was
produced, 1 otherwise (an `error` field explains why).
