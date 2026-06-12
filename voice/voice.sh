#!/bin/bash
# voice.sh — push-to-talk voice loop for the brain router. See README.md.
#
# Flow: tap Enter -> ffmpeg records mic -> whisper-cli transcribes (language auto)
#       -> brain router (system/brain/router.py, vault-whitelisted, --resume memory)
#       -> strip markdown -> TTS (kokoro|elevenlabs|say) -> afplay.
#       Say "goodbye" / Ctrl-C to quit.
#
# Built for bash 3.2 (macOS default): no ${var,,}, guarded array expansions.

set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Repo root: resolved from this script's location (voice.sh lives at <root>/voice/).
# Override with PAI_ROOT when running from elsewhere.
ROOT="${PAI_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# Repo-side files (git-tracked code): this script, config, python helpers.
VOICE_DIR="$ROOT/voice"
# Runtime-side files (machine-local, never in git): venv, models, cache, secrets, log.
export VOICE_RUNTIME="${VOICE_RUNTIME:-$HOME/.config/personal-ai/voice}"
mkdir -p "$VOICE_RUNTIME"

if [ -f "$VOICE_DIR/config.env" ]; then
  # shellcheck disable=SC1090
  source "$VOICE_DIR/config.env"
else
  echo "voice: missing $VOICE_DIR/config.env — copy config.env.example to config.env and adjust" >&2
  exit 1
fi
# Secrets are optional (only needed for the elevenlabs provider / Telegram bridge).
# shellcheck disable=SC1090
[ -f "$VOICE_RUNTIME/secrets.env" ] && source "$VOICE_RUNTIME/secrets.env"

# Python for the helpers (capture daemon, VAD, brain call). Defaults to the
# runtime venv created during setup; falls back to whatever python3 is on PATH.
PY="${VOICE_PYTHON:-$VOICE_RUNTIME/.venv/bin/python}"
[ -x "$PY" ] || PY="python3"
# Kokoro helper runs on the same interpreter unless config points elsewhere.
[ -x "${KOKORO_PY:-}" ] || KOKORO_PY="$PY"

# Brain router — text in, text out. Lives in the repo; override via VOICE_BRAIN.
VOICE_BRAIN="${VOICE_BRAIN:-$ROOT/system/brain/router.py}"

SESSION_FILE="$VOICE_RUNTIME/.session"
CACHE_DIR="$VOICE_RUNTIME/cache"
LOG="$VOICE_RUNTIME/voice.log"
TRIGGER_FIFO="$VOICE_RUNTIME/.trigger.fifo"
CONTROL_FIFO="$VOICE_RUNTIME/.control.fifo"
IDLE_FLAG="$VOICE_RUNTIME/.idle"          # sentinel: main loop is waiting for a trigger
HANDSFREE="${VOICE_HANDSFREE:-1}"
mkdir -p "$CACHE_DIR"
TMP="$(mktemp -d /tmp/voice.XXXXXX)"
CAP_PID=""
ENTER_PID=""
cleanup(){
  [ -n "$CAP_PID"   ] && kill "$CAP_PID"   2>/dev/null
  [ -n "$ENTER_PID" ] && kill "$ENTER_PID" 2>/dev/null
  rm -rf "$TMP"; printf "\n"
}
trap 'cleanup; exit 0' EXIT INT

ts(){ date "+%Y-%m-%d %H:%M:%S"; }
log(){ echo "[$(ts)] $*" >> "$LOG"; }
lc(){ printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Mute the wake-word listener for an entire turn (record + STT + LLM + TTS).
# The daemon's own 2 s debounce doesn't cover the whole turn, so the assistant's
# TTS could re-fire the wake word mid-reply. No-ops without handsfree.
busy_on()  { [ "$HANDSFREE" = "1" ] && printf 'busy:on\n'  >&4; }
busy_off() { [ "$HANDSFREE" = "1" ] && printf 'busy:off\n' >&4; }

# Idle sentinel: lets the Enter-toggle subshell ignore Enter mashes during a
# turn so they don't buffer as phantom toggles. Touched when the main loop is
# waiting on the FIFO; removed when it claims a trigger.
mark_idle(){ : > "$IDLE_FLAG" 2>/dev/null; }
mark_busy(){ rm -f "$IDLE_FLAG" 2>/dev/null; }

# --- cancellable wait (barge-in) --------------------------------------------
# Block until process $1 exits OR the operator presses Enter to cancel it.
# bash 3.2 has no fractional `read -t` and no `read -t 0` probe, so we can't
# poll — instead a background watcher does ONE blocking read on the active
# input channel and kills $1 the instant a cancel arrives; when $1 finishes on
# its own we kill the (still-blocked) watcher. Cancel travels the trigger FIFO
# in handsfree mode (fd 3, token "cancel" emitted by the Enter-toggle subshell)
# and plain stdin otherwise (any line = cancel). Sets globals:
#   CANCELLED = 1 if the operator cancelled, else 0
#   PROC_RC   = exit code of $1 (130 when cancelled)
await_or_cancel(){
  local pid="$1" t
  CANCELLED=0
  rm -f "$TMP/.cancelled"
  # NOTE: bash reassigns a backgrounded command's stdin to /dev/null (POSIX async
  # rule). The handsfree watcher reads the trigger FIFO on fd 3 (inherited, so
  # unaffected); the non-handsfree watcher must explicitly reattach /dev/tty or it
  # would read instant-EOF and never see the operator's Enter.
  if [ "$HANDSFREE" = "1" ]; then
    (
      while IFS= read -r -u 3 t; do
        [ "$t" = "cancel" ] && { kill "$pid" 2>/dev/null; : > "$TMP/.cancelled"; break; }
      done
    ) 2>/dev/null &
  else
    (
      while IFS= read -r t; do
        kill "$pid" 2>/dev/null; : > "$TMP/.cancelled"; break   # any line = cancel
      done
    ) < /dev/tty 2>/dev/null &
  fi
  local w=$!
  wait "$pid" 2>/dev/null; PROC_RC=$?
  kill "$w" 2>/dev/null; wait "$w" 2>/dev/null
  if [ -f "$TMP/.cancelled" ]; then CANCELLED=1; PROC_RC=130; rm -f "$TMP/.cancelled"; fi
}

# --- play with voice barge-in (handsfree + BARGE_IN=1 only) -----------------
# Play $1 while racing THREE things: the playback, a Silero VAD listening for the
# operator to talk over the reply, and the Enter-cancel watcher. First to land wins.
# bash 3.2 has no `wait -n`, so we poll liveness with `kill -0` + fractional sleep.
# Sets globals:
#   BARGEDIN  = 1 if the operator spoke over the reply ($wav now holds their turn)
#   CANCELLED = 1 if Enter cancelled playback (no new turn)
# Self-trigger caveat: on open speakers the VAD can fire on the assistant's own
# TTS — that's why BARGE_IN defaults off and BARGE_IN_THRESHOLD is high (see
# config.env).
play_with_bargein(){
  local out="$1" vrc
  BARGEDIN=0; CANCELLED=0
  rm -f "$TMP/.cancelled"

  afplay "$out" & local ap=$!
  # VAD records the interruption straight into $wav and exits 0 on speech-onset.
  # Long pre-speech window so it stays alive for the whole reply; we kill it when
  # playback ends on its own.
  "$PY" "$VOICE_DIR/vad-capture.py" "$wav" \
    --threshold "$BARGE_IN_THRESHOLD" --pre-speech-ms 600000 >>"$LOG" 2>&1 & local vp=$!
  # Enter-cancel watcher (handsfree emits "cancel" on the trigger FIFO when busy).
  ( while IFS= read -r -u 3 t; do [ "$t" = "cancel" ] && { : > "$TMP/.cancelled"; break; }; done ) 2>/dev/null & local cw=$!

  while :; do
    if [ -f "$TMP/.cancelled" ]; then kill "$ap" "$vp" 2>/dev/null; CANCELLED=1; break; fi
    if ! kill -0 "$ap" 2>/dev/null; then kill "$vp" 2>/dev/null; break; fi   # playback done → stop listening
    if [ -n "$vp" ] && ! kill -0 "$vp" 2>/dev/null; then                     # VAD exited on its own
      wait "$vp" 2>/dev/null; vrc=$?
      if [ "$vrc" -eq 0 ]; then kill "$ap" 2>/dev/null; BARGEDIN=1; break; fi # 0 = captured a barge-in
      vp=""                                                                   # timeout/misfire → let playback finish
    fi
    sleep 0.1
  done

  kill "$cw" "$ap" "$vp" 2>/dev/null
  wait "$ap" 2>/dev/null; wait "$vp" 2>/dev/null; wait "$cw" 2>/dev/null
  rm -f "$TMP/.cancelled"
}

# ======================================================================
#  PRESENTATION LAYER  (cosmetic only — no pipeline logic lives here)
#  Terminal HUD: green frame and labels, dim-green machine/status text,
#  gold for the assistant's reply, amber pulse for the live mic.
# ======================================================================

# Colors (256-color SGR; degrade harmlessly on dumb terminals).
if [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; then
  C_RST=$'\033[0m'; C_B=$'\033[1m'; C_DIM=$'\033[2m'
  C_GRN=$'\033[38;5;48m'    # green   ~#33FF66  (frame / labels)
  C_GRD=$'\033[38;5;28m'    # dim green        (machine / status text)
  C_GLD=$'\033[38;5;179m'   # gold    ~#E8B84B (assistant's reply)
  C_AMB=$'\033[38;5;208m'   # amber            (live recording)
  C_RED=$'\033[38;5;167m'   # soft red         (errors)
  C_GRY=$'\033[38;5;240m'   # muted grey       (hints)
else
  C_RST=''; C_B=''; C_DIM=''; C_GRN=''; C_GRD=''; C_GLD=''; C_AMB=''; C_RED=''; C_GRY=''
fi

# Layout probe — pick fullscreen vs compact each call (handles resize).
ui_cols(){ tput cols 2>/dev/null || echo 80; }
ui_rows(){ tput lines 2>/dev/null || echo 24; }
ui_compact(){ [ "$(ui_cols)" -lt 56 ] || [ "$(ui_rows)" -lt 14 ]; }

# Repeat a string $2 times -> stdout.  rep "─" 40
rep(){ local s="$1" n="$2" o=""; while [ "$n" -gt 0 ]; do o="$o$s"; n=$((n-1)); done; printf '%s' "$o"; }

# ---- Banner ----------------------------------------------------------
# Mic glyph on the left, letterspaced wordmark to the right. No frame, so
# there's no multibyte border-alignment to fight. Gold glyph, green wordmark,
# dim "push to talk" tagline. Collapses to a one-liner on a narrow pane.
banner(){
  if [ "$(ui_cols)" -lt 30 ]; then
    printf '\n %s◉%s  %sV O I C E%s\n' "$C_GLD" "$C_RST" "$C_B$C_GRN" "$C_RST"
    return
  fi
  printf '\n'
  printf '%s   ▄█▄%s\n'                          "$C_GLD" "$C_RST"
  printf '%s   ███%s     %sV O I C E%s\n'        "$C_GLD" "$C_RST" "$C_B$C_GRN" "$C_RST"
  printf '%s   ─┴─%s     %spush to talk%s\n'     "$C_GLD" "$C_RST" "$C_DIM$C_GRD" "$C_RST"
}

# ---- Status / prompt strings ----------------------------------------
# Idle prompt: green ▸ caret.  Compact pane gets a terse glyph-only cue.
prompt_idle(){
  if ui_compact; then printf '%s\n %s◉%s %stalk%s %s▸%s ' \
      "" "$C_GRN" "$C_RST" "$C_DIM$C_GRD" "$C_RST" "$C_GRN" "$C_RST"
  else printf '%s\n %s◉%s  press %sEnter%s to talk  %s▸%s ' \
      "" "$C_GRN" "$C_RST" "$C_B$C_GRN" "$C_RST" "$C_GRN" "$C_RST"; fi
}
# Recording prompt: amber ● + "REC" — unmistakably live.
prompt_rec(){
  if ui_compact; then printf ' %s●%s %sREC%s %sstop%s %s▸%s ' \
      "$C_AMB$C_B" "$C_RST" "$C_AMB" "$C_RST" "$C_DIM$C_GRD" "$C_RST" "$C_AMB" "$C_RST"
  else printf ' %s● REC%s  recording…  press %sEnter%s to stop  %s▸%s ' \
      "$C_AMB$C_B" "$C_RST" "$C_B$C_GRN" "$C_RST" "$C_AMB" "$C_RST"; fi
}
# Follow-up prompt: dim cue that we're awake without a fresh wake-word.
prompt_followup(){
  if ui_compact; then printf ' %s↺%s %sFU%s %s▸%s ' \
      "$C_AMB" "$C_RST" "$C_DIM$C_GRD" "$C_RST" "$C_AMB" "$C_RST"
  else printf '   %s↺%s  follow-up?  %s%s\n' \
      "$C_AMB$C_B" "$C_RST" "$C_DIM$C_GRD" "$C_RST"; fi
}

# ---- Transcript lines -----------------------------------------------
# you: dim-green machine voice (what the room heard).
line_you(){ printf '   %s%s┤ you   ├%s %s%s%s\n' "$C_DIM" "$C_GRD" "$C_RST" "$C_GRD" "$1" "$C_RST"; }
# assistant: gold (the reply).
line_assistant(){ printf '   %s%s┤ voice ├%s %s%s%s\n' "$C_B" "$C_GLD" "$C_RST" "$C_GLD" "$1" "$C_RST"; }
# transient "thinking" cue while the router works (no spinner thread — bash-3.2 safe).
line_think(){ printf '   %s%s┤ voice ├%s %s…%s\n' "$C_B" "$C_GLD" "$C_RST" "$C_DIM$C_GRD" "$C_RST"; }

# ---- Error / edge states (soft red, indented to match transcript) ----
note_warn(){ printf '   %s⚠ %s%s\n' "$C_RED" "$1" "$C_RST"; }
note_hint(){ printf '     %s%s%s\n' "$C_GRY" "$1" "$C_RST"; }

# --- synth $1=text -> $2=output path. Returns 0 on success, 1 on failure.
#     Provider chosen by $TTS_PROVIDER (kokoro|elevenlabs|say). Output is WAV
#     for kokoro/say, MP3 for elevenlabs — afplay handles both.
synth(){
  local text="$1" out="$2"
  case "$TTS_PROVIDER" in
    kokoro)
      "$KOKORO_PY" "$KOKORO_SCRIPT" "$text" "$out" 2>>"$LOG" || return 1
      [ -s "$out" ] || return 1
      return 0
      ;;
    elevenlabs)
      local payload code
      payload=$(python3 -c "import json,sys;print(json.dumps({'text':sys.argv[1],'model_id':sys.argv[2],'voice_settings':{'stability':0.5,'similarity_boost':0.8,'style':0.0}}))" "$text" "$EL_MODEL")
      code=$(curl -s -w "%{http_code}" -X POST \
        "https://api.elevenlabs.io/v1/text-to-speech/$EL_VOICE_ID" \
        -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" \
        -d "$payload" -o "$out")
      [ "$code" = "200" ] || { log "TTS elevenlabs http=$code: $(head -c 200 "$out" 2>/dev/null)"; return 1; }
      return 0
      ;;
    say)
      say -v "$SAY_FALLBACK_VOICE" -o "$out" --data-format=LEF32@22050 "$text" 2>>"$LOG" || return 1
      [ -s "$out" ] || return 1
      return 0
      ;;
    *)
      log "TTS: unknown provider '$TTS_PROVIDER'"; return 1 ;;
  esac
}

synth_ext(){
  case "$TTS_PROVIDER" in elevenlabs) echo mp3 ;; *) echo wav ;; esac
}

# --- speak dynamic text (no cache). On synth failure, fall back to `say`. ---
# Playback is cancellable: Enter mid-reply stops afplay and returns to idle
# (sets CANCELLED=1 via await_or_cancel). The `say` fallback is short and not
# wired for cancel.
say_live(){
  local out="$TMP/reply.$(synth_ext)"
  BARGEDIN=0
  if synth "$1" "$out"; then
    if [ "${BARGE_IN:-0}" = "1" ] && [ "$HANDSFREE" = "1" ]; then
      play_with_bargein "$out"     # talk over the reply to interrupt; Enter still cancels
    else
      afplay "$out" &
      await_or_cancel $!           # Enter cancels playback
    fi
  else
    note_warn "voice unavailable — using system fallback"
    say -v "$SAY_FALLBACK_VOICE" "$1"
  fi
}

# --- speak a FIXED phrase, cached by key. ---
say_fixed(){  # $1=cache-key  $2=text
  local out="$CACHE_DIR/$1.$(synth_ext)"
  if [ ! -s "$out" ]; then
    if ! synth "$2" "$out"; then
      rm -f "$out"
      note_warn "voice unavailable — using system fallback"
      say -v "$SAY_FALLBACK_VOICE" "$2"
      return
    fi
  fi
  afplay "$out"
}

# --- strip markdown/code so it reads cleanly aloud ---
clean_text(){ python3 - "$1" <<'PY'
import sys,re
t=sys.argv[1]
t=re.sub(r'```.*?```',' ',t,flags=re.S)        # fenced code
t=re.sub(r'`([^`]*)`',r'\1',t)                  # inline code
t=re.sub(r'\[(.*?)\]\([^)]*\)',r'\1',t)         # links -> label
t=re.sub(r'^[\s>#*\-]+','',t,flags=re.M)        # leading md markers
t=re.sub(r'[*_#>`|]+',' ',t)                    # stray md symbols
t=re.sub(r'\n{2,}','. ',t); t=t.replace('\n',' ')
print(re.sub(r'\s{2,}',' ',t).strip())
PY
}

# --- post-STT semantic gate ---
# Whisper hallucinates on near-silence and noise: "[BLANK_AUDIO]", "[Music]",
# "Thanks for watching.", "you.", "Subscribe.", etc. Drop those before paying
# STT downstream (LLM + TTS) tokens. Strips bracketed/parenthesized markers
# anywhere in the string, then deny-lists known one-liner hallucinations and
# pure filler. Exit 1 = drop the turn; stdout on 0 = cleaned transcript.
# Preserves real short commands (goodbye, yes, no, stop, etc.) by allow-by-default.
filter_stt(){ python3 - "$1" <<'PY'
import sys, re
t = sys.argv[1].strip()
t = re.sub(r'\[[^\]]*\]', '', t)             # [BLANK_AUDIO], [Music], [Applause], ...
t = re.sub(r'\([^)]*\)', '', t)              # (silence), (music), (laughter), ...
t = re.sub(r'\s+', ' ', t).strip()
norm = re.sub(r'[.!?,\-…"\']+$', '', t.lower()).strip()
norm = re.sub(r'^[.!?,\-…"\']+', '', norm).strip()
DENY = {
    '', 'you', 'thank you', 'thanks', 'thanks for watching',
    'thanks for watching!', 'thanks for listening', 'please subscribe',
    'subscribe', '.com', 'www', 'www.com', 'dot com',
    'uh', 'um', 'hmm', 'hm', 'mm', 'mmm', 'mhm', 'mm-hmm', 'mmhm',
    'ah', 'oh', 'eh', 'er',
}
if not any(c.isalnum() for c in t) or norm in DENY:
    sys.exit(1)
print(t)
PY
}

PERSONA='You are a concise voice assistant speaking ALOUD. Reply in ENGLISH ONLY, in plain spoken prose — no markdown, no lists, no tables, no code, no symbols, no emoji. Lead with the answer. Keep replies to ONE or two sentences; never volunteer preamble, caveats, or lists unless explicitly asked to expand. Brevity is a feature: this is spoken, not written, and shorter replies are faster and cheaper. The user may speak to you in another language; understand it, but always answer in English.'

# --- transcript: append every successful turn to a daily raw-transcript file.
# Path is dot-prefixed so an Obsidian-style indexer skips it — keeps voice
# filler (canned phrases) out of search results. A digest extractor can lift
# the meaningful content into system/voice/digest/ for retrieval.
TRANSCRIPT_DIR="$ROOT/system/voice/.transcripts-raw"
mkdir -p "$TRANSCRIPT_DIR" 2>/dev/null
transcript(){  # $1=user-said  $2=assistant-said
  local file="$TRANSCRIPT_DIR/voice-$(date +%F).md"
  if [ ! -f "$file" ]; then
    {
      echo "---"
      echo "title: Voice transcript — $(date +%F)"
      echo "tags: [voice, transcript]"
      echo "---"
      echo
    } >> "$file"
  fi
  {
    echo "## $(date +%H:%M:%S)"
    echo
    echo "**you**: $1"
    echo
    echo "**assistant**: $2"
    echo
  } >> "$file"
}

# --- vault whitelist: which vaults the router may read this session ---
# Keep this narrow — every vault listed is content a voice turn could surface.
add_dirs=()
for vault in ${READ_VAULTS:-vault1}; do
  d="$ROOT/vaults/$vault"; [ -d "$d" ] && add_dirs+=(--add-dir "$d")
done

# --- optional timeout wrapper ---
TIMEOUT=()
command -v timeout  >/dev/null 2>&1 && TIMEOUT=(timeout 150)
command -v gtimeout >/dev/null 2>&1 && TIMEOUT=(gtimeout 150)

# --- resume prior conversation if we have a session id ---
resume_args=()
[ -s "$SESSION_FILE" ] && resume_args=(--resume "$(cat "$SESSION_FILE")")

# --- banner + greeting ---
clear
banner
say_fixed greeting "Voice assistant online."
if ui_compact; then
  note_hint 'Enter ▸ talk · "goodbye" quits'
else
  printf '   %sVoice assistant online.%s\n' "$C_DIM$C_GRD" "$C_RST"
  note_hint 'Press Enter to talk, Enter again to stop · say "goodbye" or Ctrl-C to quit.'
fi

# --- handsfree FIFO setup (on by default; VOICE_HANDSFREE=0 disables) ---
# Daemon emits "hotkey:start" / "hotkey:stop" / "wake" into the FIFO.
# Enter-tap still works in handsfree mode as a manual fallback.
if [ "$HANDSFREE" = "1" ]; then
  [ -p "$TRIGGER_FIFO" ] || mkfifo "$TRIGGER_FIFO"
  exec 3<> "$TRIGGER_FIFO"   # keep FIFO open both ways so reads don't EOF
  [ -p "$CONTROL_FIFO" ] || mkfifo "$CONTROL_FIFO"
  exec 4<> "$CONTROL_FIFO"   # control channel: busy:on/off to the daemon
  # spawn the capture daemon so a single command brings up the full handsfree pipe.
  # cleanup() reaps it on exit. stderr → voice.log so pynput warnings are visible.
  "$PY" "$VOICE_DIR/capture.py" >>"$LOG" 2>&1 &
  CAP_PID=$!

  # Enter-toggle from this terminal: emit hotkey:start/stop into the trigger
  # FIFO so Enter behaves like Option-hold without globally grabbing the key.
  # Scoped to this TTY via `[ -t 0 ]` — won't fire when stdin is piped/closed.
  # Gated on the IDLE_FLAG sentinel: Enter mashes during a turn no longer
  # buffer into the FIFO as phantom toggles.
  if [ -t 0 ]; then
    (
      enter_state=0
      while IFS= read -r line; do
        if [ "$enter_state" -eq 1 ]; then
          printf 'hotkey:stop\n' >&3        # recording in progress: Enter stops it
          enter_state=0
        elif [ -f "$IDLE_FLAG" ]; then
          if [ -n "$line" ]; then
            printf 'text:%s\n' "$line" >&3  # typed turn — skip mic + Whisper
          else
            printf 'hotkey:start\n' >&3     # bare Enter — begin recording
            enter_state=1
          fi
        else
          printf 'cancel\n' >&3             # busy (thinking/speaking): Enter cancels
        fi
      done
    ) &
    ENTER_PID=$!
  fi

  note_hint "handsfree on · Enter/Option to talk · type+Enter to send text · Enter again to cancel · wake word optional"
fi

# --- main loop ---
HAVE_WAV=0   # set by the follow-up window to skip the next trigger-read
while true; do
  wav="$TMP/in.wav"
  typed=""        # set to a non-empty string for a TYPED turn (skips mic + Whisper)
  if [ "$HAVE_WAV" = "1" ]; then
    HAVE_WAV=0    # consume: wav already populated by the follow-up capture
  elif [ "$HANDSFREE" = "1" ]; then
    prompt_idle
    mark_idle    # let the Enter-subshell know we'll accept a fresh toggle
    IFS= read -r -u 3 trig || break
    mark_busy    # claim the turn — Enter mashes from here on are dropped
    case "$trig" in
      text:*)
        busy_on
        typed="${trig#text:}"    # operator typed a line instead of talking
        ;;
      hotkey:start)
        busy_on
        ffmpeg -nostdin -loglevel error -f avfoundation -i "$MIC_INDEX" -ac 1 -ar 16000 -y "$wav" &
        FF=$!
        prompt_rec
        while IFS= read -r -u 3 t2; do [ "$t2" = "hotkey:stop" ] && break; done
        kill -INT "$FF" 2>/dev/null; wait "$FF" 2>/dev/null
        ;;
      wake)
        busy_on
        prompt_rec
        # VAD-endpointed capture: silence-run + max-utt cap + pre-speech misfire.
        # Replaces a fixed-window ffmpeg -t; helper exits 1 on no-usable-speech
        # so we can soft-abort below without paying STT + LLM tokens.
        "$PY" "$VOICE_DIR/vad-capture.py" "$wav" >>"$LOG" 2>&1
        VAD_RC=$?
        if [ "$VAD_RC" -eq 1 ]; then
          note_warn "didn't catch that — try again"
          busy_off; continue
        fi
        ;;
      *) continue ;;
    esac
  else
    # non-handsfree: bare Enter records; typing a line + Enter sends a typed turn.
    IFS= read -r -p "$(prompt_idle)" line || break
    if [ -n "$line" ]; then
      typed="$line"
    else
      ffmpeg -nostdin -loglevel error -f avfoundation -i "$MIC_INDEX" -ac 1 -ar 16000 -y "$wav" &
      FF=$!
      IFS= read -r -p "$(prompt_rec)" _
      kill -INT "$FF" 2>/dev/null; wait "$FF" 2>/dev/null
    fi
  fi

  if [ -n "$typed" ]; then
    txt="$typed"        # typed turn — no audio, no Whisper, no STT filter
  else
    if [ ! -s "$wav" ]; then
      note_warn "no audio captured"
      note_hint "grant Microphone access: System Settings ▸ Privacy & Security ▸ Microphone, then retry"
      busy_off; continue
    fi

    # transcribe (text only, no timestamps, quiet)
    txt=$("$WHISPER_BIN" -m "$WHISPER_MODEL" -f "$wav" -l "$WHISPER_LANG" -nt 2>>"$LOG" \
          | tr -d '\r' | tr '\n' ' ' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if filtered=$(filter_stt "$txt"); then
      txt="$filtered"
    else
      log "stt filter dropped: '$txt'"
      note_warn "didn't catch that — try again"; busy_off; continue
    fi
  fi
  line_you "$txt"
  line_think

  case "$(lc "$txt")" in
    *goodbye*|*"good bye"*) say_fixed goodbye "Goodbye."; busy_off; break;;
  esac

  # --- brain: provider router, read-only by default ---
  # Wrapped so we can retry without --resume if the stored session has aged out
  # (the backend prints "No conversation found with session ID" to stderr and
  # exits with no JSON — which would otherwise read as a router outage).
  brain(){
    cd "$VOICE_DIR" && ${TIMEOUT[@]+"${TIMEOUT[@]}"} "$PY" "$VOICE_BRAIN" \
        --prompt "$txt" \
        --persona "$PERSONA" \
        --mode "${VOICE_BRAIN_MODE:-auto}" \
        --workspace "${VOICE_BRAIN_WORKSPACE:-$ROOT}" \
        --timeout "${VOICE_BRAIN_TIMEOUT:-150}" \
        --claude-config-dir "${VOICE_CLAUDE_CONFIG_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}" \
        --codex-sandbox "${VOICE_CODEX_SANDBOX:-read-only}" \
        ${add_dirs[@]+"${add_dirs[@]}"} "$@" \
        < /dev/null 2>>"$LOG"
  }
  # Run the brain in the background so Enter can cancel it mid-flight; the reply
  # JSON lands in a file, so a cancel simply discards it (and stops token spend).
  : > "$TMP/brain.json"
  brain ${resume_args[@]+"${resume_args[@]}"} > "$TMP/brain.json" &
  await_or_cancel $!
  json=$(cat "$TMP/brain.json" 2>/dev/null)
  if [ "$CANCELLED" = "0" ] && [ -z "$json" ] && [ ${#resume_args[@]} -gt 0 ]; then
    log "brain: --resume failed (stale session id); clearing .session and retrying fresh"
    rm -f "$SESSION_FILE"; resume_args=()
    : > "$TMP/brain.json"
    brain > "$TMP/brain.json" &
    await_or_cancel $!
    json=$(cat "$TMP/brain.json" 2>/dev/null)
  fi
  if [ "$CANCELLED" = "1" ]; then
    printf '\033[1A\033[2K'   # erase the transient "…" think line
    note_hint "cancelled"
    busy_off; continue
  fi

  # --output-format json returns an ARRAY of events; the 'result' object is last.
  reply=$(printf '%s' "$json" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin)
    if isinstance(d,list):
        rs=[e for e in d if isinstance(e,dict) and e.get('type')=='result']
        d=rs[-1] if rs else (d[-1] if d else {})
    print(d.get('result','') if isinstance(d,dict) else '')
except Exception: pass" 2>/dev/null)
  sid=$(printf '%s' "$json" | python3 -c "import sys,json
try:
    d=json.load(sys.stdin); sid=''
    if isinstance(d,list):
        for e in d:
            if isinstance(e,dict) and e.get('session_id'): sid=e['session_id']
    elif isinstance(d,dict): sid=d.get('session_id','')
    print(sid)
except Exception: pass" 2>/dev/null)
  [ -n "$sid" ] && { echo "$sid" > "$SESSION_FILE"; resume_args=(--resume "$sid"); }

  if [ -z "$reply" ]; then
    log "empty reply; json head: $(printf '%s' "$json" | head -c 300)"
    printf '\033[1A\033[2K'   # erase the transient "…" think line
    note_warn "I'm having trouble reaching the router at the moment."
    say_fixed brainfail "I'm having trouble reaching the router at the moment."
    busy_off; continue
  fi

  clean=$(clean_text "$reply")
  printf '\033[1A\033[2K'   # erase the transient "…" think line
  line_assistant "$clean"
  transcript "$txt" "$clean"
  say_live "$clean"

  # Barge-in: operator talked over the reply. $wav already holds their utterance;
  # carry it straight into the next turn with busy still on (no re-wake).
  if [ "${BARGEDIN:-0}" = "1" ]; then
    HAVE_WAV=1
    continue
  fi

  # Follow-up window: stay muted-but-listening for the next utterance so the
  # user doesn't have to re-fire the wake-word for natural conversation.
  # Interruptible — Enter during the listen cancels back to idle (so this is
  # safe to enable by default). VAD timeout or cancel => release and return to IDLE.
  # Skipped entirely if the reply's playback was cancelled.
  if [ "$CANCELLED" = "0" ] && [ "$HANDSFREE" = "1" ] && [ "${FOLLOWUP_WINDOW_MS:-0}" -gt 0 ]; then
    prompt_followup
    "$PY" "$VOICE_DIR/vad-capture.py" "$wav" \
      --pre-speech-ms "$FOLLOWUP_WINDOW_MS" >>"$LOG" 2>&1 &
    await_or_cancel $!
    if [ "$CANCELLED" = "0" ] && [ "$PROC_RC" -eq 0 ]; then
      HAVE_WAV=1   # caught speech — carry into next iteration; skip trigger-read; busy stays on
      continue
    fi
    # cancelled, or VAD timed out → fall through to idle
  fi
  busy_off
done
