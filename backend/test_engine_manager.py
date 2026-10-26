"""Verify Breeze readiness, process ownership, and model startup."""

import io
import json
import os
from types import SimpleNamespace

import pytest

from backend import engine_manager as manager


@pytest.mark.parametrize("payload,ready", [
    ({"status": "ok", "sample_rate": 24000}, True),
    ({"status": "loading"}, False),
    ({"named_endpoints": {}}, False),
    ({"status": "ok", "sample_rate": 48000}, False),
    ([], False),
])
def test_breeze_readiness_requires_its_health_contract(monkeypatch, payload, ready):
    response = io.BytesIO(json.dumps(payload).encode())
    response.status = 200
    urls = []
    monkeypatch.setattr(manager.urllib.request, "urlopen", lambda url, **kwargs: urls.append(url) or response)
    assert manager._is_ready(manager.TTS_URL) is ready
    assert urls == [f"{manager.TTS_URL}/health"]


def test_tts_starts_pinned_local_runtime(monkeypatch, tmp_path):
    root = tmp_path / "breeze-tts"
    model = root / "checkpoints" / "breeze-tts-2"
    paths = [root / "breeze_infer/api.py", root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")]
    paths.extend(model / name for name in ["config.json", "tokenizer.json", "audio_tokenizer/model.safetensors", "model.safetensors"])
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    monkeypatch.setattr(manager, "TTS_ROOT", root)
    monkeypatch.setattr(manager, "TTS_MODEL_ROOT", model)
    monkeypatch.setattr(manager, "LOG_ROOT", tmp_path)
    monkeypatch.setattr(manager, "PID_FILE", tmp_path / "engine.pid")
    calls = []
    monkeypatch.setattr(manager.subprocess, "Popen", lambda command, **kwargs: (
        calls.append((command, kwargs)) or SimpleNamespace(pid=1234)
    ))
    engine = manager.EngineManager()
    try:
        engine._start("tts")
        command, kwargs = calls[0]
        assert command[1:3] == [str(manager.PROJECT_ROOT / "scripts" / "breeze_server.py"), str(model)]
        assert "--no-fast-all" in command
        assert kwargs["cwd"] == root
        assert json.loads(manager.PID_FILE.read_text())["engine"] == "tts"
    finally:
        if engine._log_handle:
            engine._log_handle.close()


def test_missing_runtime_has_actionable_setup_error(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "TTS_ROOT", tmp_path)
    monkeypatch.setattr(manager, "PID_FILE", tmp_path / "engine.pid")
    with pytest.raises(manager.EngineError, match="setup-breeze.bat"):
        manager.EngineManager()._start("tts")


def test_process_ownership_is_scoped_to_breeze_workspace():
    def process(command):
        return SimpleNamespace(cmdline=lambda: command, children=lambda **kwargs: [])

    owned = process([str(manager.TTS_ROOT / ".venv/Scripts/python.exe"), "-m", "breeze_infer.api"])
    other = process(["C:/elsewhere/python.exe", "-m", "breeze_infer.api"])
    sibling = process([str(manager.TTS_ROOT) + "-other/.venv/python.exe", "-m", "breeze_infer.api"])
    assert manager._is_expected_process(owned, "tts")
    assert not manager._is_expected_process(other, "tts")
    assert not manager._is_expected_process(sibling, "tts")


def test_switching_to_breeze_stops_owned_music_first(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "PID_FILE", tmp_path / "engine.pid")
    engine = manager.EngineManager()
    ready = {manager.TTS_URL: False, manager.MUSIC_URL: True}
    events = []
    monkeypatch.setattr(manager, "_is_ready", lambda url: ready[url])
    monkeypatch.setattr(engine, "_owns_live_process", lambda: True)
    monkeypatch.setattr(engine, "_stop_managed", lambda: events.append("stop"))

    def start(name):
        events.append(name)
        ready[manager.TTS_URL] = True

    monkeypatch.setattr(engine, "_start", start)
    engine.ensure("tts")
    assert events == ["stop", "tts"]


def test_external_music_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(manager, "PID_FILE", tmp_path / "engine.pid")
    engine = manager.EngineManager()
    monkeypatch.setattr(manager, "_is_ready", lambda url: url == manager.MUSIC_URL)
    with pytest.raises(manager.EngineError, match="外部窗口"):
        engine.ensure("tts")


@pytest.mark.parametrize("message", ["torch.OutOfMemoryError: CUDA out of memory", "OSError: os error 1455"])
def test_startup_memory_failure_has_actionable_message(monkeypatch, tmp_path, message):
    monkeypatch.setattr(manager, "LOG_ROOT", tmp_path)
    (tmp_path / "tts.log").write_text(message, encoding="utf-8")
    assert "关闭其他大型程序" in manager.EngineManager._tail_log("tts")
