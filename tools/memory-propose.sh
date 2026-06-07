#!/usr/bin/env bash
# memory-propose — SessionEnd hook.
# Queues the just-ended session for the assistant's NEXT-START memory-review pass.
# Deterministic: condenses the transcript into a pending file. No model call (the
# assistant is the judge at next SessionStart) -> no API key, no recursion, no
# cost. Silent + fail-open: never interrupts or blocks session close.
#
# Paths resolve against VAULT_ROOT (defaults to the build root one level up from
# this script's parent). Expects a propose.py at
# ${VAULT_ROOT}/system/memory/propose.py supporting `record --transcript <p>
# --session <id>`.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_ROOT="${VAULT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROPOSE="$VAULT_ROOT/system/memory/propose.py"
[ -f "$PROPOSE" ] || exit 0

payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0

tpath="$(printf '%s' "$payload" | python3 -c \
  'import sys,json
try: print(json.load(sys.stdin).get("transcript_path",""))
except Exception: pass' 2>/dev/null)"
sid="$(printf '%s' "$payload" | python3 -c \
  'import sys,json
try: print(json.load(sys.stdin).get("session_id",""))
except Exception: pass' 2>/dev/null)"

[ -n "$tpath" ] || exit 0
python3 "$PROPOSE" record --transcript "$tpath" --session "$sid" >/dev/null 2>&1 || true
exit 0
