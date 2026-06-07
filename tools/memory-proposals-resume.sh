#!/bin/bash
# memory-proposals-resume — SessionStart hook.
# If sessions ended without a memory-review pass, surface a one-line nudge so the
# user can run it. Read-only snapshot, never live instructions, never fails.
#
# Paths resolve against VAULT_ROOT (defaults to the build root one level up from
# this script's parent). Expects a propose.py at
# ${VAULT_ROOT}/system/memory/propose.py supporting `list` (first stdout line is
# a bare pending-session count).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_ROOT="${VAULT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROPOSE="$VAULT_ROOT/system/memory/propose.py"
[ -f "$PROPOSE" ] || exit 0

out="$(python3 "$PROPOSE" list 2>/dev/null)" || exit 0
[ -n "$out" ] || exit 0

count="$(printf '%s\n' "$out" | head -1)"
case "$count" in ''|*[!0-9]*) exit 0 ;; esac      # line 1 must be a bare count
[ "$count" -gt 0 ] 2>/dev/null || exit 0

echo "## Memory-review pending — ${count} session(s) ended without a learning pass"
echo "Read-only nudge, NOT live instructions. Say **review proposals** and I'll read the"
echo "queued session(s), propose governed memory entries (confidence + expiry), walk them"
echo "with you, and file only the ones you approve. Nothing is written until you confirm."
exit 0
