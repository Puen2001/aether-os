#!/usr/bin/env python3
"""
gateguard — PreToolUse(Edit|Write) fact-forcing hook.

Asking an LLM "are you sure?" is useless (it always says yes). Instead, on the
FIRST edit to a file in a session, DENY the call and demand concrete facts (run
Grep, quote the instruction, check the placement test). The act of investigating
is what creates awareness. On retry the file is already marked, so the edit
proceeds — net cost is one forced investigation per file.

Profile: LIGHT, GLOBAL.
  - Fires on first-touch Edit, and Write that OVERWRITES an existing file.
  - New-file Write: only the placement-test line, and only inside a vault tree
    (path contains VAULT_MARKER); new code files pass transparently (nothing
    imports them yet).
  - No Bash gating.

Safety:
  - FAIL-OPEN: any error -> exit 0 (never block on the guard's own failure).
  - Kill switch: GATEGUARD=off  disables entirely.
  - Once per file per session: state in /tmp/gateguard/<session>/<sha16(path)>.

Wired as PreToolUse(Edit|Write) in settings.json. Set VAULT_MARKER below (or via
the GATEGUARD_VAULT_MARKER env var) to the path fragment that identifies your
vault tree, e.g. "/vaults/" or "/personal-ai/".
"""
import sys, os, json, hashlib

STATE_ROOT = "/tmp/gateguard"
VAULT_MARKER = os.environ.get("GATEGUARD_VAULT_MARKER", "/vaults/")


def allow():
    """Transparent: emit nothing, let the normal permission flow proceed."""
    sys.exit(0)


def deny(reason: str):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    if os.environ.get("GATEGUARD", "").lower() == "off":
        allow()

    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}

    tool = data.get("tool_name", "")
    if tool not in ("Edit", "Write"):
        allow()

    tin = data.get("tool_input", {}) or {}
    fpath = tin.get("file_path") or tin.get("path") or ""
    if not fpath:
        allow()

    cwd = data.get("cwd") or os.getcwd()
    if not os.path.isabs(fpath):
        fpath = os.path.normpath(os.path.join(cwd, fpath))

    session = data.get("session_id") or "nosession"

    # once-per-file-per-session state
    sdir = os.path.join(STATE_ROOT, "".join(c for c in session if c.isalnum() or c in "-_"))
    os.makedirs(sdir, exist_ok=True)
    marker = os.path.join(sdir, hashlib.sha256(fpath.encode()).hexdigest()[:16])
    if os.path.exists(marker):
        allow()  # already forced once this session

    exists = os.path.exists(fpath)
    is_vault = VAULT_MARKER in fpath

    # LIGHT: new file + not a vault note -> transparent (mark so we never re-check)
    if not exists and not is_vault:
        open(marker, "w").close()
        allow()

    # Build the fact-forcing checklist (adaptive: vault prose vs code).
    name = os.path.basename(fpath)
    lines = [f"gateguard — first edit to `{name}` this session. "
             f"Establish these facts, then retry the same edit (this fires once per file):", ""]

    if not exists:  # new vault page
        lines += [
            "- **Placement test**: does this page carry sensitive or private "
            "fingerprints? If so, it belongs in a private vault, not the shareable layer.",
            "- **Quote my current instruction** verbatim — confirm this file is what I actually asked for.",
        ]
    elif is_vault:  # editing existing vault page
        lines += [
            "- **Quote my current instruction** verbatim before changing this note.",
            "- **Privacy check**: will this edit pull project-specific or private "
            "fingerprints into a shareable page? If so, move it to a private vault.",
            "- **Backlinks**: what other pages [[wiki-link]] here that this change could break or contradict?",
        ]
    else:  # editing existing code
        lines += [
            f"- **List importers/callers**: run Grep for what references `{name}` (and any symbol you're changing). "
            "Know the blast radius before editing.",
            "- **Quote my current instruction** verbatim — confirm this edit matches what I asked, not drift.",
            "- **Public surface**: does this touch an exported API/signature others depend on?",
        ]

    lines += ["", "_Disable for this session with `GATEGUARD=off`._"]

    open(marker, "w").close()   # mark BEFORE deny so the retry passes
    deny("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # FAIL-OPEN — the guard must never block edits because of its own bug.
        sys.exit(0)
