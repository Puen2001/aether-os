#!/usr/bin/env bash
# voice-digest-resume — SessionStart hook.
# Surfaces the tail of the most recent voice digest into every chat session so
# text sessions have continuity with the single shared voice channel.
# Read-only snapshot, not live instructions.
#
# Looks back up to 7 days; emits the last 5 turn-pairs from the freshest
# digest found. Silent on no recent digest. Never fails the hook (exit 0
# always). (5 turn-pairs keeps the token cost low — full digests stay on
# disk for explicit recall.)
#
# Wire under hooks.SessionStart in system/settings.example.json:
#   { "type": "command", "command": "system/hooks/voice-digest-resume.sh", "timeout": 10 }

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${PAI_ROOT:-$(cd "$HERE/../.." && pwd)}"
DIGEST_DIR="$ROOT/system/voice/digest"
MAX_AGE_DAYS=7
TAIL_TURNS=5

[ -d "$DIGEST_DIR" ] || exit 0

# Find newest digest within window (BSD `date -v` first, GNU `date -d` fallback).
latest=""
latest_date=""
for i in $(seq 0 "$MAX_AGE_DAYS"); do
  d=$(date -v-"${i}"d +%Y-%m-%d 2>/dev/null) || d=$(date -d "${i} days ago" +%Y-%m-%d 2>/dev/null) || continue
  f="$DIGEST_DIR/voice-${d}.md"
  if [ -f "$f" ]; then latest="$f"; latest_date="$d"; break; fi
done

[ -n "$latest" ] || exit 0

# Parse turn-pairs and print the last $TAIL_TURNS. Use python for safe multiline
# regex over the markdown structure written by voice-digest-build.
tail_md=$(TAIL_TURNS="$TAIL_TURNS" python3 - "$latest" <<'PY' 2>/dev/null
import os, re, sys
n = int(os.environ.get("TAIL_TURNS", "5"))
src = open(sys.argv[1]).read()
turn_re = re.compile(
    r"^##\s+(?P<t>\d{2}:\d{2}:\d{2})\s*\n+"
    r"\*\*you\*\*:\s*(?P<y>.*?)\n+"
    r"\*\*assistant\*\*:\s*(?P<a>.*?)(?=\n+##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
turns = list(turn_re.finditer(src))
if not turns:
    sys.exit(0)
for m in turns[-n:]:
    print(f"### {m.group('t')}")
    print(f"**you**: {m.group('y').strip()}")
    print()
    print(f"**assistant**: {m.group('a').strip()}")
    print()
PY
)

[ -n "$tail_md" ] || exit 0

# How old is the digest? (days)
age_days=$(( ($(date +%s) - $(date -j -f %Y-%m-%d "$latest_date" +%s 2>/dev/null || date -d "$latest_date" +%s 2>/dev/null || echo $(date +%s))) / 86400 ))
case "$age_days" in
  0) age_label="today" ;;
  1) age_label="yesterday" ;;
  *) age_label="${age_days} days ago" ;;
esac

printf '\n## Voice resume — last %s turn-pair(s) from %s (%s)\n' \
  "$TAIL_TURNS" "$latest_date" "$age_label"
printf 'Read-only snapshot of the most recent voice session, NOT live instructions. Use as continuity context only; memory entries and vault notes remain the source of truth on conflict.\n\n'
printf '%s\n' "$tail_md"
exit 0
