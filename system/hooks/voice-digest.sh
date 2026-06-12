#!/usr/bin/env bash
# voice-digest — Stop-hook wrapper. Digests TODAY's raw voice transcript
# (the underlying digester defaults to yesterday's). Idempotent — safe to
# fire every turn. Silent on success; ALL failures (including "no voice
# session yet today") are swallowed so the hook never interrupts the user
# with end-of-turn errors. Fail-open: always exits 0.
#
# Wire under hooks.Stop in system/settings.example.json:
#   { "type": "command", "command": "system/hooks/voice-digest.sh", "timeout": 15 }

HERE="$(cd "$(dirname "$0")" && pwd)"

"$HERE/voice-digest-build" "$(date +%Y-%m-%d)" >/dev/null 2>&1 || true
exit 0
