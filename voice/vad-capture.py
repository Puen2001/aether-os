#!/usr/bin/env python3
"""VAD-endpointed mic capture for the wake-word turn path.

Records from the default input until either:
  * `--silence-ms` of contiguous non-speech AFTER speech has started, or
  * `--max-utt-ms` wall-clock cap from speech start, or
  * `--pre-speech-ms` passes with no speech detected at all (misfire).

Writes a 16 kHz mono 16-bit WAV to <out_path> and exits 0 on a usable capture.
Exits 1 on "no usable speech" (too short / no speech) so the bash loop can
silently abort the turn instead of round-tripping garbage through STT + LLM.

Replaces a fixed `ffmpeg -t 5` capture on the wake path. The hotkey path is
unchanged — the user already signals end-of-turn by releasing the key.

Model: Silero VAD v5 ONNX, run via onnxruntime (already in the venv as an
openwakeword dep). Downloaded on first run to
$VOICE_RUNTIME/models/silero_vad.onnx (default runtime dir:
~/.config/personal-ai/voice).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SR = 16000
CHUNK = 512  # samples; Silero's required window at 16 kHz (32 ms)
CHUNK_MS = CHUNK / SR * 1000.0

VOICE_RUNTIME = Path(os.environ.get("VOICE_RUNTIME",
                                    Path.home() / ".config/personal-ai/voice"))
MODELS_DIR = VOICE_RUNTIME / "models"
MODEL_PATH = MODELS_DIR / "silero_vad.onnx"
MODEL_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"
LOG_PATH = VOICE_RUNTIME / "voice.log"


def log(msg: str) -> None:
    try:
        with LOG_PATH.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] vad-capture: {msg}\n")
    except OSError:
        pass


def ensure_model() -> Path:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1024:
        return MODEL_PATH
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    log(f"downloading silero VAD model to {MODEL_PATH}")
    tmp = MODEL_PATH.with_suffix(".onnx.part")
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp)
        tmp.replace(MODEL_PATH)
        log(f"model downloaded ({MODEL_PATH.stat().st_size} bytes)")
    except Exception as e:
        log(f"model download failed: {e}")
        raise
    return MODEL_PATH


class SileroVAD:
    def __init__(self, model_path: Path):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(model_path), sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        self.sr_input = np.array(SR, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)

    def __call__(self, chunk_int16: np.ndarray) -> float:
        x = (chunk_int16.astype(np.float32) / 32768.0).reshape(1, -1)
        out, self.state = self.session.run(
            None, {"input": x, "state": self.state, "sr": self.sr_input}
        )
        return float(out[0][0])


def parse_device(spec):
    if spec is None or spec == "":
        return None
    return int(spec) if spec.isdigit() else spec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_path")
    ap.add_argument("--silence-ms", type=int,
                    default=int(os.environ.get("VAD_SILENCE_MS", "800")))
    ap.add_argument("--max-utt-ms", type=int,
                    default=int(os.environ.get("VAD_MAX_UTT_MS", "30000")))
    ap.add_argument("--min-utt-ms", type=int,
                    default=int(os.environ.get("VAD_MIN_UTT_MS", "600")))
    ap.add_argument("--pre-speech-ms", type=int,
                    default=int(os.environ.get("VAD_PRE_SPEECH_MS", "3000")))
    ap.add_argument("--threshold", type=float,
                    default=float(os.environ.get("VAD_THRESHOLD", "0.5")))
    ap.add_argument("--device",
                    default=os.environ.get("VAD_DEVICE"))
    args = ap.parse_args()

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    silence_chunks_needed = max(1, int(round(args.silence_ms / CHUNK_MS)))
    max_total_chunks = max(1, int(round(args.max_utt_ms / CHUNK_MS)))
    min_speech_chunks = max(1, int(round(args.min_utt_ms / CHUNK_MS)))
    pre_speech_chunks = max(1, int(round(args.pre_speech_ms / CHUNK_MS)))

    try:
        ensure_model()
    except Exception:
        return 2  # distinct from "no speech" — infra failure

    vad = SileroVAD(MODEL_PATH)
    device = parse_device(args.device)

    captured = []
    speech_started = False
    silent_run = 0
    pre_speech_seen = 0
    total_chunks = 0
    speech_chunks = 0

    log(f"capture start out={out_path.name} thr={args.threshold} "
        f"silence_ms={args.silence_ms} max_utt_ms={args.max_utt_ms} "
        f"min_utt_ms={args.min_utt_ms} pre_speech_ms={args.pre_speech_ms} "
        f"device={device!r}")

    try:
        with sd.InputStream(channels=1, samplerate=SR, blocksize=CHUNK,
                            dtype="int16", device=device) as stream:
            while True:
                data, overflow = stream.read(CHUNK)
                if overflow:
                    log("input overflow")
                mono = np.asarray(data[:, 0], dtype=np.int16)
                captured.append(mono)
                total_chunks += 1

                p = vad(mono)
                is_speech = p >= args.threshold

                if not speech_started:
                    pre_speech_seen += 1
                    if is_speech:
                        speech_started = True
                        speech_chunks = 1
                        silent_run = 0
                        log(f"speech start @ {total_chunks} p={p:.2f}")
                    elif pre_speech_seen >= pre_speech_chunks:
                        log("no speech within pre-speech window")
                        return 1
                else:
                    if is_speech:
                        silent_run = 0
                        speech_chunks += 1
                    else:
                        silent_run += 1
                        if silent_run >= silence_chunks_needed:
                            log(f"silence end @ {total_chunks} "
                                f"speech_chunks={speech_chunks}")
                            break
                    if total_chunks >= max_total_chunks:
                        log(f"max-utt cap @ {total_chunks}")
                        break
    except sd.PortAudioError as e:
        log(f"audio error: {e}")
        return 2

    if speech_chunks < min_speech_chunks:
        log(f"too short: speech_chunks={speech_chunks} < min={min_speech_chunks}")
        return 1

    audio = np.concatenate(captured)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio.tobytes())
    log(f"wrote {out_path.name} samples={audio.shape[0]} "
        f"dur={audio.shape[0]/SR:.2f}s speech={speech_chunks*CHUNK_MS/1000:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
