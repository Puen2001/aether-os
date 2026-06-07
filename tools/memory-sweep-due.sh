#!/bin/bash
# memory-sweep-due — SessionStart hook (memory-governance cadence detector).
# Surfaces a single line when the memory-governance sweep is due (>=90 days
# since the last one, or never run). Detection only — never runs the sweep
# itself (that would hijack the session); the user runs the sweep manually.
#
# READ-ONLY. Silent on the happy path. Never fails the hook (exit 0 always).
#
# Paths resolve against VAULT_ROOT (defaults to the build root one level up from
# this script's parent). The sweep script is expected at
# ${VAULT_ROOT}/system/memory/sweep.py and writes its last-run date to
# ${VAULT_ROOT}/system/memory/.last-sweep. Adjust to taste.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_ROOT="${VAULT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SWEEP_PY="$VAULT_ROOT/system/memory/sweep.py"
LAST="$VAULT_ROOT/system/memory/.last-sweep"
INTERVAL_DAYS=90

{
  [ -f "$SWEEP_PY" ] || exit 0

  now=$(date +%s)
  if [ -f "$LAST" ]; then
    last_date=$(tr -d '[:space:]' < "$LAST")
    last_s=$(date -j -f %Y-%m-%d "$last_date" +%s 2>/dev/null \
             || date -d "$last_date" +%s 2>/dev/null || echo "")
    [ -n "$last_s" ] || exit 0
    age_days=$(( (now - last_s) / 86400 ))
    [ "$age_days" -ge "$INTERVAL_DAYS" ] || exit 0
    due_msg="last sweep ${age_days}d ago"
  else
    due_msg="never run"
  fi

  # Best-effort flagged count (dry-run is fast; tolerate any failure).
  flagged=$(python3 "$SWEEP_PY" --dry-run 2>/dev/null \
            | sed -n "s/.*'flagged': \([0-9]*\).*/\1/p" | head -1)
  [ -n "$flagged" ] || flagged="?"

  printf '\nmemory sweep due (%s · %s flagged) — run the memory sweep\n' \
    "$due_msg" "$flagged"
} 2>/dev/null || true

exit 0
