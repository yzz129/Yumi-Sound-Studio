"""Filesystem and service configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
TTS_ROOT = WORKSPACE_ROOT / "index-tts-2.5"
MUSIC_ROOT = WORKSPACE_ROOT / "ACE-Step-1.5"
RUNTIME_ROOT = PROJECT_ROOT / "runtime"
UPLOAD_ROOT = RUNTIME_ROOT / "uploads"
OUTPUT_ROOT = RUNTIME_ROOT / "outputs"
LOG_ROOT = RUNTIME_ROOT / "logs"
PID_FILE = RUNTIME_ROOT / "engine.pid"

TTS_URL = "http://127.0.0.1:7860"
MUSIC_URL = "http://127.0.0.1:7861"

for directory in (UPLOAD_ROOT, OUTPUT_ROOT, LOG_ROOT):
    directory.mkdir(parents=True, exist_ok=True)

