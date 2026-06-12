#!/usr/bin/env python3
"""Voice capture daemon (handsfree triggers).

Emits a single line into the trigger FIFO whenever a turn should start:
- "hotkey:start" / "hotkey:stop"  — right-Option pressed / released
- "wake"                          — wake word detected (openWakeWord)

The bash loop (voice.sh) reads the FIFO and runs its existing
record -> transcribe -> reply path. This daemon does not touch the microphone
during recording; it pauses the wake-word listener while a turn is in flight.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path

VOICE_RUNTIME = Path(os.environ.get("VOICE_RUNTIME",
                                    Path.home() / ".config/personal-ai/voice"))
FIFO = VOICE_RUNTIME / ".trigger.fifo"
CONTROL_FIFO = VOICE_RUNTIME / ".control.fifo"
LOG = VOICE_RUNTIME / "voice.log"

WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.6"))
# Stock openWakeWord model name; train/drop in a custom .onnx to change the phrase.
WAKE_MODEL = os.environ.get("WAKE_MODEL", "hey_jarvis")
WAKE_ENABLED = os.environ.get("VOICE_WAKE_ENABLED", "0") == "1"  # opt-in


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] capture: {msg}\n")


def ensure_fifo() -> None:
    for path in (FIFO, CONTROL_FIFO):
        if path.exists() and not path.is_fifo():
            path.unlink()
        if not path.exists():
            os.mkfifo(path)


def emit(line: str) -> None:
    try:
        fd = os.open(FIFO, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, (line + "\n").encode())
        os.close(fd)
    except OSError as e:
        # no reader on the FIFO — bash loop isn't up. Log so the next
        # "doesn't work" leaves a trail instead of vanishing silently.
        log(f"emit dropped {line!r}: {e}")


# `busy` is the wake-listener mute signal — set/cleared by the bash control
# FIFO around every turn (record + STT + LLM + TTS + optional follow-up).
# `hotkey_active` is the hotkey state machine — tracks whether a press is
# currently held down. The two were tangled in an earlier version: on_release
# used to clear `busy`, which prematurely unmuted the wake listener during a
# follow-up and also let stray Option releases corrupt turn state. Keeping
# them separate fixes that.
busy = threading.Event()
hotkey_active = threading.Event()
HOTKEY_DEBOUNCE_MS = 200  # collapses pynput's macOS modifier-key double-fire
_last_hotkey_press_ms = 0.0


def hotkey_listener() -> None:
    from pynput import keyboard

    # Default to right-Option only — `alt` matches BOTH Option keys, which on
    # macOS made the duplicate-emit bug worse. Set VOICE_HOTKEY=alt to opt back.
    pref = os.environ.get("VOICE_HOTKEY", "alt_r").lower()
    if pref == "alt":
        triggers = {keyboard.Key.alt, keyboard.Key.alt_r}
    else:
        triggers = {keyboard.Key.alt_r}
    log(f"hotkey listener: triggers={[t.name for t in triggers]}")

    def on_press(key):
        global _last_hotkey_press_ms
        if key not in triggers:
            return
        now_ms = time.monotonic() * 1000
        if now_ms - _last_hotkey_press_ms < HOTKEY_DEBOUNCE_MS:
            return  # macOS modifier-key double-fire
        if hotkey_active.is_set() or busy.is_set():
            return  # already in a turn — don't queue a phantom
        _last_hotkey_press_ms = now_ms
        hotkey_active.set()
        log(f"hotkey press: {getattr(key, 'name', key)}")
        emit("hotkey:start")

    def on_release(key):
        if key not in triggers:
            return
        if not hotkey_active.is_set():
            return
        hotkey_active.clear()
        log(f"hotkey release: {getattr(key, 'name', key)}")
        emit("hotkey:stop")
        # Note: do NOT touch `busy` here — that's owned by the bash control FIFO.

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def control_listener() -> None:
    # Bash side writes "busy:on" at turn start and "busy:off" after TTS finishes,
    # so the wake-word listener stays muted for the whole turn (STT + LLM + TTS),
    # not just the 2 s local debounce. Without this, the assistant's own TTS can
    # re-fire the wake word mid-reply.
    log("control listener up")
    fd = os.open(CONTROL_FIFO, os.O_RDWR)
    with os.fdopen(fd, "r") as f:
        for line in f:
            cmd = line.strip()
            if cmd == "busy:on":
                busy.set()
                log("busy:on (control)")
            elif cmd == "busy:off":
                busy.clear()
                log("busy:off (control)")


def wake_listener() -> None:
    try:
        import sounddevice as sd
        from openwakeword.model import Model
    except ImportError as e:
        log(f"wake disabled — missing dep: {e}")
        return

    model = Model(wakeword_models=[WAKE_MODEL])
    sample_rate = 16000
    chunk = 1280  # 80ms at 16kHz, matches openwakeword expectations

    def callback(indata, frames, time_info, status):
        if busy.is_set():
            return
        scores = model.predict(indata[:, 0])
        for name, score in scores.items():
            if score >= WAKE_THRESHOLD:
                log(f"wake fired: {name}={score:.2f}")
                busy.set()
                emit("wake")
                time.sleep(2.0)  # debounce — bash loop owns the mic now
                busy.clear()

    with sd.InputStream(channels=1, samplerate=sample_rate, blocksize=chunk,
                        dtype="int16", callback=callback):
        while True:
            time.sleep(1)


def main() -> None:
    ensure_fifo()
    log(f"daemon up (wake={'on' if WAKE_ENABLED else 'off'})")
    threads = [
        threading.Thread(target=hotkey_listener, daemon=True),
        threading.Thread(target=control_listener, daemon=True),
    ]
    if WAKE_ENABLED:
        threads.append(threading.Thread(target=wake_listener, daemon=True))
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log("daemon stopping")


if __name__ == "__main__":
    main()
