#!/usr/bin/env python3
"""One-shot Kokoro TTS. Usage: kokoro-synth.py "<text>" <output.wav>

Model files (kokoro-v1.0.onnx + voices-v1.0.bin) are expected under the
runtime models dir; download them from the kokoro-onnx release page (see
README.md). All knobs are env vars so the caller (voice.sh / a bridge)
controls voice and speed without CLI churn.
"""
import os
import sys

import soundfile as sf
from kokoro_onnx import Kokoro

_DEFAULT_MODELS = os.path.expanduser("~/.config/personal-ai/voice/models/kokoro")
MODEL = os.environ.get("KOKORO_MODEL", f"{_DEFAULT_MODELS}/kokoro-v1.0.onnx")
VOICES = os.environ.get("KOKORO_VOICES", f"{_DEFAULT_MODELS}/voices-v1.0.bin")
VOICE = os.environ.get("KOKORO_VOICE", "bm_daniel")
LANG = os.environ.get("KOKORO_LANG", "en-gb")
SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))

text, out = sys.argv[1], sys.argv[2]
k = Kokoro(MODEL, VOICES)
audio, sr = k.create(text, voice=VOICE, speed=SPEED, lang=LANG)
sf.write(out, audio, sr)
