#!/usr/bin/env python3
"""Brain router.

One CLI contract for assistant front-ends (voice, Telegram):
  prompt + persona + optional session id -> JSON {result, session_id, provider}.

Backends are pluggable. Pick one with --provider / BRAIN_PROVIDER:
  claude  shell out to the Claude Code CLI (headless, read-only tools)
  codex   shell out to the Codex CLI (read-only sandbox)
  api     POST to any OpenAI-compatible /chat/completions endpoint --
          works with a local model (Ollama, LM Studio, vLLM, llama.cpp
          server) or a hosted API (OpenAI, OpenRouter, Together, ...)
  cmd     pipe the prompt through an arbitrary local command (BRAIN_CMD),
          e.g. `ollama run llama3.1`, `llm -m ...`, any chat CLI

No backend is required to be installed -- configure the one you have. The
front-ends never bind to a provider directly, so the same voice/Telegram
stack runs on whatever brain you point it at.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


# Repo root: this script lives at <root>/system/brain/router.py.
ROOT = Path(os.environ.get("PAI_ROOT") or Path(__file__).resolve().parents[2])

DEFAULT_ALLOWED_TOOLS = ("Read", "Glob", "Grep")
CLAUDE_ENV_STRIP = (
    "CLAUDECODE",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST",
    "CLAUDE_CONFIG_DIR",
)

# Providers that ship their own code/review specialization. For these, auto
# mode sends code-shaped prompts to Codex; the universal backends (api, cmd)
# answer every prompt themselves.
CLI_DUO = ("claude", "codex")

REVIEW_RE = re.compile(
    r"\b(review|pr|pull request|diff|uncommitted|regression|security audit)\b",
    re.I,
)
CODE_RE = re.compile(
    r"\b("
    r"code|coding|debug|bug|fix|repo|repository|file|files|script|program|"
    r"python|typescript|javascript|react|node|bash|shell|git|test|tests|"
    r"build|lint|compile|stack trace|traceback|exception|error|refactor|"
    r"function|class|api|cli|mcp|server|frontend|backend"
    r")\b",
    re.I,
)


@dataclass
class BackendResult:
    provider: str
    result: str = ""
    session_id: str = ""
    status: str = "ok"
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok" and bool(self.result.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route prompts to a pluggable LLM backend.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--persona", default="")
    parser.add_argument("--mode", default=os.environ.get("BRAIN_MODE", "auto"),
                        choices=("auto", "claude", "codex", "review", "both", "api", "cmd"))
    parser.add_argument("--provider", default=os.environ.get("BRAIN_PROVIDER", "claude"),
                        choices=("claude", "codex", "api", "cmd"),
                        help="default backend for auto-mode general prompts")
    parser.add_argument("--resume", default="")
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument("--allowed-tool", action="append", default=list(DEFAULT_ALLOWED_TOOLS))
    parser.add_argument("--workspace", default=os.environ.get(
        "BRAIN_WORKSPACE",
        str(ROOT),
    ))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("BRAIN_TIMEOUT", "150")))
    parser.add_argument("--claude-model", default=os.environ.get("BRAIN_CLAUDE_MODEL", ""))
    parser.add_argument("--claude-config-dir", default=os.environ.get("BRAIN_CLAUDE_CONFIG_DIR", ""))
    parser.add_argument("--codex-model", default=os.environ.get("BRAIN_CODEX_MODEL", ""))
    parser.add_argument("--codex-sandbox", default=os.environ.get("BRAIN_CODEX_SANDBOX", "read-only"),
                        choices=("read-only", "workspace-write", "danger-full-access"))
    parser.add_argument("--codex-persist", action="store_true",
                        default=os.environ.get("BRAIN_CODEX_PERSIST", "0") == "1")
    # OpenAI-compatible API backend (provider/mode = api).
    parser.add_argument("--api-base", default=os.environ.get(
        "BRAIN_API_BASE", "https://api.openai.com/v1"))
    parser.add_argument("--api-key", default=os.environ.get("BRAIN_API_KEY", ""))
    parser.add_argument("--api-model", default=os.environ.get("BRAIN_MODEL", "gpt-4o-mini"))
    # Generic command backend (provider/mode = cmd).
    parser.add_argument("--cmd", default=os.environ.get("BRAIN_CMD", ""))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def choose_route(prompt: str, mode: str, provider: str) -> str:
    if mode != "auto":
        return mode
    if provider in CLI_DUO:
        if CODE_RE.search(prompt) or REVIEW_RE.search(prompt):
            return "codex"
        return "claude"
    # api / cmd handle every prompt themselves.
    return provider


def trim_text(text: str, limit: int = 4000) -> str:
    text = re.sub(r"\s+\n", "\n", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n[truncated]"


def assistant_system_prompt(persona: str) -> str:
    """Shared system prompt for the provider-neutral backends (api, cmd)."""
    base = (
        "You are a backend brain for a personal assistant. Answer the user's prompt "
        "directly. Do not claim to edit files, create commits, or take destructive "
        "actions. Keep the answer concise and suitable for being read aloud unless the "
        "user asks for detail."
    )
    persona = persona.strip()
    if persona:
        return f"{base}\n\nVoice/persona constraints:\n{persona}"
    return base


def claude_env(config_dir: str = "") -> dict[str, str]:
    env = os.environ.copy()
    for key in CLAUDE_ENV_STRIP:
        env.pop(key, None)
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = str(Path(config_dir).expanduser())
    return env


def parse_claude_json(stdout: str) -> tuple[str, str]:
    payload = json.loads(stdout)
    if isinstance(payload, list):
        result_events = [
            event for event in payload
            if isinstance(event, dict) and event.get("type") == "result"
        ]
        last = result_events[-1] if result_events else (payload[-1] if payload else {})
        result = last.get("result", "") if isinstance(last, dict) else ""
        session_id = ""
        for event in payload:
            if isinstance(event, dict) and event.get("session_id"):
                session_id = str(event["session_id"])
        return result, session_id
    if isinstance(payload, dict):
        return str(payload.get("result", "") or ""), str(payload.get("session_id", "") or "")
    return "", ""


def claude_control_error(result: str) -> str:
    text = result.strip()
    low = text.lower()
    if low.startswith("not logged in"):
        return text
    if "hit your session limit" in low:
        return text
    return ""


def run_claude(args: argparse.Namespace) -> BackendResult:
    if not shutil.which("claude"):
        return BackendResult("claude", status="error", error="claude CLI not found")

    cmd = [
        "claude", "-p", args.prompt,
        "--append-system-prompt", args.persona,
        "--output-format", "json",
    ]
    for directory in args.add_dir:
        cmd += ["--add-dir", directory]
    if args.allowed_tool:
        cmd += ["--allowedTools", *args.allowed_tool]
    if args.resume:
        cmd += ["--resume", args.resume]
    if args.claude_model:
        cmd += ["--model", args.claude_model]

    try:
        completed = subprocess.run(
            cmd,
            cwd=args.workspace,
            env=claude_env(args.claude_config_dir),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        return BackendResult("claude", status="error", error=f"timeout after {args.timeout}s")
    except OSError as exc:
        return BackendResult("claude", status="error", error=str(exc))

    if not completed.stdout.strip():
        error = trim_text(completed.stderr or f"empty stdout, rc={completed.returncode}", 1000)
        return BackendResult("claude", status="error", error=error)
    try:
        result, session_id = parse_claude_json(completed.stdout)
    except Exception as exc:
        return BackendResult(
            "claude",
            status="error",
            error=f"json parse failed: {exc}; stdout={trim_text(completed.stdout, 600)}",
        )
    if not result.strip():
        return BackendResult("claude", session_id=session_id, status="error", error="empty result")
    control_error = claude_control_error(result)
    if control_error:
        return BackendResult("claude", session_id=session_id, status="error", error=control_error)
    return BackendResult("claude", result=result, session_id=session_id)


def codex_prompt(args: argparse.Namespace, role: str) -> str:
    persona = args.persona.strip()
    constraints = (
        "You are a backend brain for a personal assistant. Answer the user's prompt directly. "
        "Do not edit files, create commits, or run destructive actions. "
        "Keep the answer concise and suitable for being read aloud unless the user asks for detail."
    )
    if role == "review":
        constraints = (
            "You are Codex reviewing the current repository for a personal assistant. "
            "Prioritize concrete bugs, regressions, security risks, and missing tests. "
            "Do not edit files."
        )
    parts = [constraints]
    if persona:
        parts.append(f"Voice/persona constraints:\n{persona}")
    parts.append(f"User prompt:\n{args.prompt}")
    return "\n\n".join(parts)


def run_codex_exec(args: argparse.Namespace, role: str = "codex") -> BackendResult:
    if not shutil.which("codex"):
        return BackendResult(role, status="error", error="codex CLI not found")

    with tempfile.TemporaryDirectory(prefix="brain-codex.") as temp_dir:
        out_file = Path(temp_dir) / "last-message.txt"
        cmd = [
            "codex", "exec",
            "--cd", args.workspace,
            "--sandbox", args.codex_sandbox,
            "--color", "never",
            "--output-last-message", str(out_file),
        ]
        if not args.codex_persist:
            cmd.append("--ephemeral")
        if args.codex_model:
            cmd += ["--model", args.codex_model]
        cmd.append("-")
        try:
            completed = subprocess.run(
                cmd,
                input=codex_prompt(args, role),
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired:
            return BackendResult(role, status="error", error=f"timeout after {args.timeout}s")
        except OSError as exc:
            return BackendResult(role, status="error", error=str(exc))

        result = out_file.read_text(errors="replace").strip() if out_file.exists() else ""
        if not result:
            result = completed.stdout.strip()
        if completed.returncode != 0 and not result:
            return BackendResult(role, status="error", error=trim_text(completed.stderr, 1200))
        if not result:
            return BackendResult(role, status="error", error="empty result")
        return BackendResult(role, result=result)


def run_codex_review(args: argparse.Namespace) -> BackendResult:
    if not shutil.which("codex"):
        return BackendResult("codex-review", status="error", error="codex CLI not found")

    cmd = [
        "codex", "-C", args.workspace,
        "-s", args.codex_sandbox,
    ]
    if args.codex_model:
        cmd += ["--model", args.codex_model]
    cmd += ["review", "--uncommitted", "-"]
    try:
        completed = subprocess.run(
            cmd,
            input=codex_prompt(args, "review"),
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        return BackendResult("codex-review", status="error", error=f"timeout after {args.timeout}s")
    except OSError as exc:
        return BackendResult("codex-review", status="error", error=str(exc))

    result = completed.stdout.strip()
    if completed.returncode != 0 and not result:
        return BackendResult("codex-review", status="error", error=trim_text(completed.stderr, 1200))
    if not result:
        return BackendResult("codex-review", status="error", error="empty result")
    return BackendResult("codex-review", result=result)


def run_api(args: argparse.Namespace) -> BackendResult:
    """OpenAI-compatible /chat/completions. Local server or hosted API."""
    url = args.api_base.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": args.api_model,
        "messages": [
            {"role": "system", "content": assistant_system_prompt(args.persona)},
            {"role": "user", "content": args.prompt},
        ],
        "temperature": 0.4,
        "stream": False,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        return BackendResult("api", status="error", error=f"HTTP {exc.code}: {trim_text(detail, 500)}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return BackendResult("api", status="error", error=f"api unreachable: {exc}")
    except Exception as exc:
        return BackendResult("api", status="error", error=str(exc))

    try:
        result = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        return BackendResult("api", status="error", error=f"unexpected response shape: {exc}")
    if not result:
        return BackendResult("api", status="error", error="empty result")
    return BackendResult("api", result=result)


def run_cmd(args: argparse.Namespace) -> BackendResult:
    """Pipe the prompt through an arbitrary local chat command (BRAIN_CMD)."""
    if not args.cmd.strip():
        return BackendResult("cmd", status="error", error="BRAIN_CMD not set")
    try:
        argv = shlex.split(args.cmd)
    except ValueError as exc:
        return BackendResult("cmd", status="error", error=f"bad BRAIN_CMD: {exc}")
    if not argv or not shutil.which(argv[0]):
        return BackendResult("cmd", status="error", error=f"command not found: {args.cmd}")

    stdin_text = f"{assistant_system_prompt(args.persona)}\n\nUser prompt:\n{args.prompt}\n"
    try:
        completed = subprocess.run(
            argv,
            input=stdin_text,
            cwd=args.workspace,
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        return BackendResult("cmd", status="error", error=f"timeout after {args.timeout}s")
    except OSError as exc:
        return BackendResult("cmd", status="error", error=str(exc))

    result = completed.stdout.strip()
    if completed.returncode != 0 and not result:
        return BackendResult("cmd", status="error", error=trim_text(completed.stderr, 1200))
    if not result:
        return BackendResult("cmd", status="error", error="empty result")
    return BackendResult("cmd", result=result)


def run_route(route: str, args: argparse.Namespace) -> list[BackendResult]:
    """Run one route, with auto-mode fallback only inside the Claude/Codex duo."""
    if route == "claude":
        results = [run_claude(args)]
        if args.mode == "auto" and not results[0].ok:
            results.append(run_codex_exec(args))
        return results
    if route == "codex":
        results = [run_codex_exec(args)]
        if args.mode == "auto" and not results[0].ok:
            results.append(run_claude(args))
        return results
    if route == "review":
        return [run_codex_review(args)]
    if route == "api":
        return [run_api(args)]
    if route == "cmd":
        return [run_cmd(args)]
    if route == "both":
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_claude, args), executor.submit(run_codex_exec, args)]
            return [future.result() for future in futures]
    return [BackendResult(route, status="error", error=f"unknown route: {route}")]


def combine_results(route: str, results: list[BackendResult]) -> tuple[str, str, str]:
    ok = [result for result in results if result.ok]
    if not ok:
        errors = "; ".join(f"{result.provider}: {result.error}" for result in results if result.error)
        return "", "", errors or "all providers returned empty results"
    if len(ok) == 1:
        return ok[0].result, ok[0].session_id, ""

    claude = next((result for result in ok if result.provider == "claude"), None)
    codex = next((result for result in ok if result.provider != "claude"), None)
    session_id = claude.session_id if claude else ""
    if route == "both":
        answer = (
            f"Primary answer:\n{trim_text(claude.result if claude else ok[0].result)}\n\n"
            f"Code check:\n{trim_text(codex.result if codex else ok[-1].result)}"
        )
        return answer, session_id, ""
    return ok[0].result, ok[0].session_id, ""


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser()
    args.workspace = str(workspace)

    route = choose_route(args.prompt, args.mode, args.provider)
    if args.dry_run:
        print(json.dumps({
            "type": "result",
            "result": "",
            "session_id": args.resume,
            "route": route,
            "provider": route,
            "dry_run": True,
        }))
        return 0

    results = run_route(route, args)

    answer, session_id, error = combine_results(route, results)
    payload = {
        "type": "result",
        "result": answer,
        "session_id": session_id,
        "route": route,
        "provider": ",".join(result.provider for result in results),
        "providers": [asdict(result) for result in results],
    }
    if error:
        payload["error"] = error
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if answer else 1


if __name__ == "__main__":
    raise SystemExit(main())
