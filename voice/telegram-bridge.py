#!/usr/bin/env python3
# Telegram voice bridge — same brain as the push-to-talk voice pack, reachable
# from the phone. Voice notes in -> voice notes out (plus a text mirror).
#
#   tg voice  -> ffmpeg (ogg/opus -> wav 16k mono) -> whisper-cli
#   tg text   -> straight to brain
#       -> shared brain router (pluggable backend, vault-scoped, --resume)
#       -> strip markdown -> TTS (kokoro|elevenlabs|say) -> ffmpeg -> ogg/opus
#       -> sendVoice + sendMessage
#
# Session memory is shared with the push-to-talk voice pack via .session so a
# turn on the desktop mic continues seamlessly on the phone. Single-process
# long-poll loop; designed to run under launchd. Rejects any sender not in
# TELEGRAM_ALLOWED_USERS.

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import requests

# --------------------------------------------------------------------- paths
HOME = Path.home()
SCRIPT_DIR = Path(__file__).resolve().parent
# Repo root: this script lives at <root>/voice/telegram-bridge.py.
ROOT = Path(os.environ.get("PAI_ROOT") or SCRIPT_DIR.parent)
RUNTIME_DIR = Path(os.environ.get("VOICE_RUNTIME") or HOME / ".config/personal-ai/voice")
CONFIG_ENV = SCRIPT_DIR / "config.env"
SECRETS_ENV = RUNTIME_DIR / "secrets.env"
SESSION_FILE = RUNTIME_DIR / ".session"
OFFSET_FILE = RUNTIME_DIR / ".telegram-offset"
LOG_FILE = RUNTIME_DIR / "voice.log"

# --------------------------------------------------------------------- env
def _load_env_file(path: Path) -> dict:
    """Parse a shell-style KEY=VALUE / KEY="VALUE" file. Strips trailing `# ...`
    comments outside quotes. Expands ${VAR}, ${VAR:-default}, and $HOME."""
    import shlex
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, rest = line.partition("=")
        key = key.strip()
        # shlex respects quoting and stops at the first unquoted '#'
        try:
            tokens = shlex.split(rest, comments=True, posix=True)
        except ValueError:
            tokens = [rest]
        val = tokens[0] if tokens else ""
        val = re.sub(r"\$\{?(\w+)(?::-([^}]*))?\}?",
                     lambda m: out.get(m.group(1), os.environ.get(m.group(1), m.group(2) or "")),
                     val)
        val = val.replace("$HOME", str(HOME))
        out[key] = val
    return out

CFG = _load_env_file(CONFIG_ENV)
SEC = _load_env_file(SECRETS_ENV)

VAULTS_DIR = Path(CFG.get("VAULTS_DIR", str(ROOT / "vaults")))
WHISPER_BIN = CFG.get("WHISPER_BIN", "/opt/homebrew/bin/whisper-cli")
WHISPER_MODEL = CFG.get("WHISPER_MODEL", str(RUNTIME_DIR / "models/ggml-small.bin"))
WHISPER_LANG = CFG.get("WHISPER_LANG", "auto")
READ_VAULTS = CFG.get("READ_VAULTS", "vault1").split()
VOICE_BRAIN = Path(CFG.get("VOICE_BRAIN", str(ROOT / "system/brain/router.py")))
VOICE_BRAIN_MODE = os.environ.get("VOICE_BRAIN_MODE", CFG.get("VOICE_BRAIN_MODE", "auto"))
VOICE_BRAIN_WORKSPACE = CFG.get("VOICE_BRAIN_WORKSPACE", str(ROOT))
VOICE_BRAIN_TIMEOUT = CFG.get("VOICE_BRAIN_TIMEOUT", "150")
VOICE_CLAUDE_CONFIG_DIR = CFG.get("VOICE_CLAUDE_CONFIG_DIR", "")
VOICE_CODEX_SANDBOX = CFG.get("VOICE_CODEX_SANDBOX", "read-only")
EL_MODEL = CFG.get("EL_MODEL", "eleven_multilingual_v2")
EL_VOICE_ID = CFG.get("EL_VOICE_ID", "<your-voice-id>")
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", CFG.get("TTS_PROVIDER", "kokoro"))
KOKORO_PY = CFG.get("KOKORO_PY", str(RUNTIME_DIR / ".venv/bin/python"))
KOKORO_SCRIPT = CFG.get("KOKORO_SCRIPT", str(SCRIPT_DIR / "kokoro-synth.py"))
SAY_FALLBACK_VOICE = CFG.get("SAY_FALLBACK_VOICE", "Daniel")

for k in ("KOKORO_MODEL", "KOKORO_VOICES", "KOKORO_VOICE", "KOKORO_LANG"):
    if k in CFG:
        os.environ.setdefault(k, CFG[k])

# Brain backend knobs are read by the router from its environment (we do not
# pass them as flags), so propagate them from config.env / secrets.env to the
# router subprocess. setdefault keeps any value already exported in the shell.
for k in ("BRAIN_PROVIDER", "BRAIN_API_BASE", "BRAIN_MODEL", "BRAIN_CMD"):
    if CFG.get(k):
        os.environ.setdefault(k, CFG[k])
if SEC.get("BRAIN_API_KEY"):
    os.environ.setdefault("BRAIN_API_KEY", SEC["BRAIN_API_KEY"])

BOT_TOKEN = SEC.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
EL_KEY = SEC.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")
ALLOWED = {s.strip() for s in (
    SEC.get("TELEGRAM_ALLOWED_USERS") or os.environ.get("TELEGRAM_ALLOWED_USERS", "")
).split(",") if s.strip()}

PERSONA = (
    "You are a concise voice assistant speaking ALOUD. "
    "Reply in ENGLISH ONLY, in short plain spoken sentences suitable for "
    "text-to-speech - no markdown, no lists, no tables, no code, no symbols, "
    "no emoji. Keep replies short: 1 to 3 sentences unless explicitly asked "
    "for detail. The user may speak to you in another language; understand it, "
    "but always answer in English."
)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

# --------------------------------------------------------------------- log
_BOT_URL_RE = re.compile(r"/bot\d+:[A-Za-z0-9_-]+")

def _redact(s: str) -> str:
    """Strip the bot token from any text before it hits a log/stderr. The token
    leaks via requests exception reprs that embed the full request URL."""
    if BOT_TOKEN:
        s = s.replace(BOT_TOKEN, "<TOKEN>")
    return _BOT_URL_RE.sub("/bot<TOKEN>", s)

def log(msg: str) -> None:
    line = _redact(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] tg: {msg}\n")
    try:
        with LOG_FILE.open("a") as f:
            f.write(line)
    except Exception:
        pass
    sys.stderr.write(line)
    sys.stderr.flush()

# --------------------------------------------------------------------- markdown -> spoken
def clean_text(t: str) -> str:
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^[\s>#*\-]+", "", t, flags=re.M)
    t = re.sub(r"[*_#>`|]+", " ", t)
    t = re.sub(r"\n{2,}", ". ", t).replace("\n", " ")
    return re.sub(r"\s{2,}", " ", t).strip()

# --------------------------------------------------------------------- telegram api
def tg(method: str, **params) -> dict:
    r = requests.post(f"{API}/{method}", json=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"telegram {method} failed: {data}")
    return data["result"]

def tg_upload(method: str, chat_id: int, field: str, file_path: Path, **extra) -> dict:
    with file_path.open("rb") as f:
        r = requests.post(
            f"{API}/{method}",
            data={"chat_id": chat_id, **extra},
            files={field: (file_path.name, f, "application/octet-stream")},
            timeout=180,
        )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"telegram {method} (upload) failed: {data}")
    return data["result"]

def tg_download(file_id: str, dest: Path) -> None:
    meta = tg("getFile", file_id=file_id)
    path = meta["file_path"]
    with requests.get(f"{FILE_API}/{path}", stream=True, timeout=120) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(64 * 1024):
                f.write(chunk)

# --------------------------------------------------------------------- pipeline pieces
def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, **kwargs)
    except FileNotFoundError as e:
        # missing binary (e.g. whisper-cli / kokoro venv) -> graceful failed result;
        # callers check returncode and fall back to text instead of crashing the turn.
        log(f"missing binary {cmd[0]!r}: {e}")
        return subprocess.CompletedProcess(cmd, 127, b"", str(e).encode())

def transcribe(audio: Path) -> str:
    """oga/opus or wav -> 16k mono wav -> whisper-cli text."""
    wav = audio.with_suffix(".16k.wav")
    cp = run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
              "-i", str(audio), "-ar", "16000", "-ac", "1", str(wav)])
    if cp.returncode != 0 or not wav.exists() or wav.stat().st_size == 0:
        log(f"ffmpeg decode failed: {cp.stderr[:200]!r}")
        return ""
    cp = run([WHISPER_BIN, "-m", WHISPER_MODEL, "-f", str(wav), "-l", WHISPER_LANG, "-nt"])
    text = (cp.stdout or b"").decode("utf-8", "replace").replace("\r", " ").replace("\n", " ").strip()
    if "[BLANK_AUDIO]" in text or "(silence)" in text:
        return ""
    return text

def brain(prompt: str) -> tuple[str, str]:
    """Returns (reply_text, session_id) through the shared brain router."""
    add_dirs: list[str] = []
    for vault in READ_VAULTS:
        d = VAULTS_DIR / vault
        if d.is_dir():
            add_dirs += ["--add-dir", str(d)]

    def call(resume_id: str | None) -> tuple[str, str]:
        cmd = [sys.executable, str(VOICE_BRAIN),
               "--prompt", prompt,
               "--persona", PERSONA,
               "--mode", VOICE_BRAIN_MODE,
               "--workspace", VOICE_BRAIN_WORKSPACE,
               "--timeout", VOICE_BRAIN_TIMEOUT,
               "--claude-config-dir", VOICE_CLAUDE_CONFIG_DIR,
               "--codex-sandbox", VOICE_CODEX_SANDBOX,
               *add_dirs]
        if resume_id:
            cmd += ["--resume", resume_id]
        cp = subprocess.run(cmd, cwd=str(SCRIPT_DIR),
                            stdin=subprocess.DEVNULL,
                            capture_output=True, text=True,
                            timeout=int(VOICE_BRAIN_TIMEOUT) + 10)
        if cp.stderr:
            log(f"brain stderr head (resume={bool(resume_id)}): {cp.stderr[:200]!r}")
        if not cp.stdout.strip():
            log(f"brain empty stdout (resume={bool(resume_id)}, rc={cp.returncode})")
            return "", ""
        try:
            d = json.loads(cp.stdout)
        except Exception:
            log(f"brain json parse failed (resume={bool(resume_id)}); head: {cp.stdout[:200]!r}")
            return "", ""
        reply, sid = "", ""
        if isinstance(d, list):
            results = [e for e in d if isinstance(e, dict) and e.get("type") == "result"]
            last = results[-1] if results else (d[-1] if d else {})
            if isinstance(last, dict):
                reply = last.get("result", "") or ""
            for e in d:
                if isinstance(e, dict) and e.get("session_id"):
                    sid = e["session_id"]
        elif isinstance(d, dict):
            reply = d.get("result", "") or ""
            sid = d.get("session_id", "") or ""
        return reply, sid

    resume_id = None
    if SESSION_FILE.exists():
        s = SESSION_FILE.read_text().strip()
        if s:
            resume_id = s
    reply, sid = call(resume_id)
    if not reply and resume_id:
        log("brain: --resume failed, retrying fresh")
        try:
            SESSION_FILE.unlink()
        except FileNotFoundError:
            pass
        reply, sid = call(None)
    if sid:
        SESSION_FILE.write_text(sid)
    return reply, sid

def synthesize(text: str, out_path: Path) -> bool:
    """Write TTS audio to the given path. Provider-specific format; caller transcodes."""
    if TTS_PROVIDER == "kokoro":
        cp = run([KOKORO_PY, KOKORO_SCRIPT, text, str(out_path)])
        if cp.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            log(f"kokoro failed: {cp.stderr[:200]!r}")
            return False
        return True
    if TTS_PROVIDER == "elevenlabs":
        if not EL_KEY:
            log("elevenlabs selected but ELEVENLABS_API_KEY missing")
            return False
        payload = {"text": text, "model_id": EL_MODEL,
                   "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0}}
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}",
            headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
            json=payload, timeout=60,
        )
        if r.status_code != 200:
            log(f"elevenlabs http={r.status_code}: {r.text[:200]!r}")
            return False
        out_path.write_bytes(r.content)
        return True
    if TTS_PROVIDER == "say":
        cp = run(["say", "-v", SAY_FALLBACK_VOICE, "-o", str(out_path),
                  "--data-format=LEF32@22050", text])
        return cp.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
    log(f"unknown TTS_PROVIDER={TTS_PROVIDER!r}")
    return False

def to_voice_ogg(src: Path, dst: Path) -> bool:
    """Transcode TTS output to ogg/opus for Telegram sendVoice."""
    cp = run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
              "-i", str(src), "-c:a", "libopus", "-b:a", "48k", str(dst)])
    return cp.returncode == 0 and dst.exists() and dst.stat().st_size > 0

# --------------------------------------------------------------------- transcript
def transcript_append(user_text: str, assistant_text: str, channel: str) -> None:
    d = ROOT / "system" / "voice" / ".transcripts-raw"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log(f"transcript mkdir failed: {e}")
        return
    f = d / f"voice-{date.today():%Y-%m-%d}.md"
    new = not f.exists()
    try:
        with f.open("a") as fp:
            if new:
                fp.write("---\n"
                         f"title: Voice transcript — {date.today():%Y-%m-%d}\n"
                         "tags: [voice, transcript]\n"
                         "---\n\n")
            fp.write(f"## {datetime.now():%H:%M:%S} ({channel})\n\n"
                     f"**you**: {user_text}\n\n"
                     f"**assistant**: {assistant_text}\n\n")
    except Exception as e:
        log(f"transcript write failed: {e}")

# --------------------------------------------------------------------- turn handler
def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    sender = str(msg.get("from", {}).get("id", ""))
    if ALLOWED and sender not in ALLOWED:
        log(f"rejecting sender={sender!r} (not in allowlist)")
        return

    with tempfile.TemporaryDirectory(prefix="voice-tg.") as td:
        tdp = Path(td)
        user_text = ""
        channel = "tg"

        if "voice" in msg or "audio" in msg:
            audio = msg.get("voice") or msg.get("audio")
            file_id = audio["file_id"]
            try:
                tg("sendChatAction", chat_id=chat_id, action="typing")
            except Exception:
                pass
            src = tdp / "in.oga"
            try:
                tg_download(file_id, src)
            except Exception as e:
                log(f"download failed: {e}")
                tg("sendMessage", chat_id=chat_id,
                   text="Couldn't fetch that voice note.")
                return
            user_text = transcribe(src)
            channel = "tg-voice"
            if not user_text:
                tg("sendMessage", chat_id=chat_id, text="Didn't catch that — try again.")
                return
            log(f"stt[{channel}]: {user_text[:200]!r}")
        elif msg.get("text"):
            user_text = msg["text"].strip()
            channel = "tg-text"
        else:
            return  # photo/sticker/etc — ignore quietly

        try:
            tg("sendChatAction", chat_id=chat_id, action="record_voice")
        except Exception:
            pass

        reply, _ = brain(user_text)
        if not reply:
            log(f"brain returned empty for prompt: {user_text[:200]!r}")
            tg("sendMessage", chat_id=chat_id,
               text="I'm having trouble reaching my brain at the moment.")
            return
        log(f"reply[{channel}]: {reply[:160]!r}")

        spoken = clean_text(reply)
        transcript_append(user_text, spoken, channel)

        ext = "mp3" if TTS_PROVIDER == "elevenlabs" else "wav"
        tts_out = tdp / f"reply.{ext}"
        if synthesize(spoken, tts_out):
            ogg = tdp / "reply.ogg"
            if to_voice_ogg(tts_out, ogg):
                try:
                    tg_upload("sendVoice", chat_id, "voice", ogg, caption=spoken[:1024])
                    log(f"sendVoice ok ({ogg.stat().st_size} bytes)")
                    return
                except Exception as e:
                    log(f"sendVoice failed: {e!r}")
            else:
                log("to_voice_ogg failed — falling back to text")
        else:
            log("synthesize failed — falling back to text")
        tg("sendMessage", chat_id=chat_id, text=spoken[:4000])
        log("text fallback sent")

# --------------------------------------------------------------------- main loop
def offset_load() -> int:
    try:
        return int(OFFSET_FILE.read_text().strip() or 0)
    except Exception:
        return 0

def offset_save(n: int) -> None:
    try:
        OFFSET_FILE.write_text(str(n))
    except Exception as e:
        log(f"offset save failed: {e}")

_running = True
def _stop(*_):
    global _running
    _running = False

def main() -> int:
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass  # log/offset/session writers degrade gracefully
    if not BOT_TOKEN:
        log("TELEGRAM_BOT_TOKEN missing — refusing to start")
        return 2
    if not shutil.which("ffmpeg"):
        log("ffmpeg not on PATH — refusing to start")
        return 2
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        me = tg("getMe")
        log(f"connected as @{me.get('username')} (id={me.get('id')})")
    except Exception as e:
        log(f"getMe failed: {e}")
        return 3
    if not ALLOWED:
        log("WARNING: TELEGRAM_ALLOWED_USERS empty — bot will refuse every message")

    offset = offset_load()
    backoff = 1.0
    while _running:
        try:
            r = requests.get(
                f"{API}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message"])},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"getUpdates: {data}")
            backoff = 1.0
            for upd in data.get("result", []):
                offset = max(offset, upd["update_id"] + 1)
                offset_save(offset)
                msg = upd.get("message")
                if not msg:
                    continue
                try:
                    handle_message(msg)
                except Exception as e:
                    log(f"handle_message crashed: {e!r}")
                    try:
                        tg("sendMessage", chat_id=msg["chat"]["id"],
                           text="Something went wrong. Logged for review.")
                    except Exception:
                        pass
        except requests.exceptions.ReadTimeout:
            continue
        except Exception as e:
            log(f"poll error: {e!r} (backoff {backoff:.0f}s)")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
    log("shutting down")
    return 0

if __name__ == "__main__":
    sys.exit(main())
