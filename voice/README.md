# voice/ — local voice interface

Talk to your brain router out loud. Audio is recorded and transcribed locally
(whisper.cpp), the text goes through `system/brain/router.py` (the same router
every other channel uses), and the reply is spoken back through a local or
cloud TTS provider. macOS only as shipped (uses `ffmpeg -f avfoundation`,
`afplay`, and `say`); the Python helpers are portable.

## Pipeline

```
mic ── ffmpeg / VAD capture ──> whisper-cli (local STT, language auto-detect)
                                     │
                                     v
                       system/brain/router.py
                       (text in -> text out, vault-whitelisted,
                        --resume session memory)
                                     │
                                     v
              strip markdown ──> TTS (kokoro | elevenlabs | say) ──> speaker
```

Replies are always spoken English; input language is auto-detected per turn,
so you can speak any Whisper-supported language.

## Modes

| Mode | Trigger | End of turn |
|---|---|---|
| Push-to-talk | tap Enter | tap Enter again |
| Typed turn | type text + Enter | — (skips mic + Whisper) |
| Handsfree hold-key | hold right Option (`VOICE_HOTKEY`) | release the key |
| Wake word | say the wake phrase (`VOICE_WAKE_ENABLED=1`) | VAD detects end of speech |
| Barge-in | start talking over the reply (`BARGE_IN=1`, headphones) | VAD endpointing |
| Follow-up window | just keep talking after a reply (`FOLLOWUP_WINDOW_MS`) | VAD endpointing |

Handsfree is on by default (`VOICE_HANDSFREE=0` for the plain Enter-only
loop). Enter is the universal cancel: it stops recording, kills an in-flight
router call (and its token spend), stops playback, and closes the follow-up
window, depending on state. Say "goodbye" or Ctrl-C to quit.

## Setup

1. System deps (macOS):

   ```bash
   brew install ffmpeg whisper-cpp
   ```

2. Python venv (runtime-local, outside the repo):

   ```bash
   python3 -m venv ~/.config/personal-ai/voice/.venv
   ~/.config/personal-ai/voice/.venv/bin/pip install -r voice/requirements.txt
   ```

3. Models (into `~/.config/personal-ai/voice/models/`):
   - Whisper STT: `ggml-small.bin` from https://huggingface.co/ggerganov/whisper.cpp
   - Kokoro TTS: `kokoro-v1.0.onnx` + `voices-v1.0.bin` from
     https://github.com/thewh1teagle/kokoro-onnx into `models/kokoro/`
   - Silero VAD: downloaded automatically on first VAD use.

4. Config:

   ```bash
   cp voice/config.env.example voice/config.env   # adjust mic index etc.; gitignore it
   ```

5. Secrets (optional — only for the elevenlabs provider / Telegram bridge):

   ```bash
   cp voice/secrets.env.example ~/.config/personal-ai/voice/secrets.env
   chmod 600 ~/.config/personal-ai/voice/secrets.env
   ```

6. Run:

   ```bash
   ./voice/voice.sh
   ```

   First run prompts for Microphone permission; handsfree additionally needs
   Accessibility permission (pynput's global hotkey listener) for your
   terminal app.

## Files

| File | Role |
|---|---|
| `voice.sh` | main loop: record, transcribe, route, speak; HUD; cancel/barge-in plumbing |
| `capture.py` | handsfree daemon: hold-key + wake-word triggers over a FIFO |
| `vad-capture.py` | Silero-VAD endpointed mic capture (wake turns, follow-ups, barge-in) |
| `kokoro-synth.py` | one-shot local TTS (text -> WAV) |
| `config.env.example` | all tunables, commented — copy to `config.env` |
| `secrets.env.example` | credential placeholders — copy to the runtime dir, chmod 600 |
| `requirements.txt` | python deps for the three helpers |

Runtime state lives in `~/.config/personal-ai/voice/` (override:
`VOICE_RUNTIME`): the venv, models, cached fixed phrases (`cache/`), the log
(`voice.log`), the trigger/control FIFOs, and `.session` — the persisted
`--resume` id that gives the router cross-turn memory. `.session` is shared
with the Telegram bridge pack, so a conversation started at the mic can
continue from your phone. Transcripts of successful turns are appended to
`<root>/system/voice/.transcripts-raw/voice-YYYY-MM-DD.md` (dot-prefixed so
vault indexers skip the raw filler); a digest step can lift the substance into
`<root>/system/voice/digest/`.

The repo root is resolved from the script's own location; override with
`PAI_ROOT` if you run it from elsewhere.

## Key knobs

All knobs live in `config.env` (each documented inline there). The headline
ones:

- `READ_VAULTS` — which vaults the router may read during a voice session.
  Keep narrow: anything listed can be read aloud or sent to a cloud model.
- `TTS_PROVIDER` — `kokoro` (free, local, default), `elevenlabs` (cloud,
  needs `ELEVENLABS_API_KEY`), `say` (macOS built-in).
- `VOICE_BRAIN_MODE` — `auto` routes conversation vs code-shaped turns to
  different backends; force with `claude`, `codex`, `review`, or `both`.
- `VOICE_CODEX_SANDBOX` — `read-only` by default so voice sessions can
  inspect but never edit.
- `VAD_*` — endpointing feel: how much silence ends a turn, the max
  utterance cap, the misfire window, the speech-probability threshold.
- `FOLLOWUP_WINDOW_MS` / `BARGE_IN` / `BARGE_IN_THRESHOLD` — conversation
  flow; see config comments for the speakers-vs-headphones caveat.

Fixed phrases (greeting, goodbye, error) are synthesized once and cached
under `cache/`, so cloud TTS credits are only spent on dynamic replies.

## Troubleshooting

- "no audio captured" — the terminal lacks mic permission. System Settings ->
  Privacy & Security -> Microphone -> enable your terminal. Test:
  `ffmpeg -f avfoundation -i ":0" -t 3 -y /tmp/m.wav && afplay /tmp/m.wav`.
- Mic dead inside tmux — the tmux server holds the mic context. Run in a
  plain terminal, or `brew install reattach-to-user-namespace`, add
  `set-option -g default-command "reattach-to-user-namespace -l $SHELL"` to
  your tmux conf, then restart the tmux server from a mic-allowed terminal.
- "voice unavailable" with elevenlabs — check `voice.log`; an HTTP 401
  usually means the key is missing the Text-to-Speech / Voices(read) scopes.
- "trouble reaching the router" — check `voice.log`; usually backend auth or
  a timeout. The loop auto-retries once without `--resume` when the stored
  session id has aged out.
- Hotkey does nothing — grant Accessibility permission to the terminal app
  (pynput needs it), then restart `voice.sh`.
