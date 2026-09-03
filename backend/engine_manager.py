"""Start, stop, and inspect the two GPU-heavy model services."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

import psutil
from loguru import logger

from .config import LOG_ROOT, MUSIC_ROOT, MUSIC_URL, PID_FILE, TTS_ROOT, TTS_URL

EngineName = Literal["tts", "music"]


class EngineError(RuntimeError):
    """Raised when a model service cannot be safely managed."""


class EngineManager:
    """Own one local model process at a time to avoid GPU memory exhaustion."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._engine: EngineName | None = None
        self._log_handle = None
        self._adopt_pid_file()

    def status(self) -> dict[str, object]:
        """Return the active service and per-engine readiness."""
        tts_ready = _is_ready(TTS_URL)
        music_ready = _is_ready(MUSIC_URL)
        active: EngineName | None = None
        if tts_ready:
            active = "tts"
        if music_ready:
            active = "music"
        return {
            "active": active,
            "tts_ready": tts_ready,
            "music_ready": music_ready,
            "busy": self._process is not None and self._process.poll() is None and not active,
        }

    def ensure(self, engine: EngineName, timeout: int = 210) -> None:
        """Ensure one requested engine is loaded, stopping the managed peer first."""
        with self._lock:
            target_url = TTS_URL if engine == "tts" else MUSIC_URL
            other_url = MUSIC_URL if engine == "tts" else TTS_URL
            if _is_ready(target_url):
                self._engine = engine
                return
            if _is_ready(other_url):
                if not self._owns_live_process():
                    raise EngineError("检测到另一个模型由外部窗口启动，请先关闭它再切换引擎。")
                self._stop_managed()
            elif self._owns_live_process():
                self._stop_managed()

            self._start(engine)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if _is_ready(target_url):
                    logger.info("{} engine is ready", engine)
                    return
                if self._process and self._process.poll() is not None:
                    raise EngineError(self._tail_log(engine))
                time.sleep(2)
            self._stop_managed()
            raise EngineError("模型启动超时，请查看 runtime/logs 中的日志。")

    def _start(self, engine: EngineName) -> None:
        root = TTS_ROOT if engine == "tts" else MUSIC_ROOT
        script = "start-webui.bat" if engine == "tts" else "start-music.bat"
        if not (root / script).exists():
            raise EngineError(f"找不到 {root / script}")

        log_path = LOG_ROOT / f"{engine}.log"
        self._log_handle = log_path.open("ab", buffering=0)
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        self._process = subprocess.Popen(
            ["cmd.exe", "/d", "/c", script],
            cwd=root,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        self._engine = engine
        PID_FILE.write_text(
            json.dumps({"pid": self._process.pid, "engine": engine}),
            encoding="utf-8",
        )
        logger.info("Started {} engine with pid {}", engine, self._process.pid)

    def _stop_managed(self) -> None:
        process = self._process
        if process is None and PID_FILE.exists():
            self._adopt_pid_file()
            process = self._process
        if process is None:
            return
        try:
            parent = psutil.Process(process.pid)
            if not _is_expected_process(parent, self._engine):
                raise EngineError("为保护其他程序，已拒绝终止无法确认来源的进程。")
            targets = parent.children(recursive=True) + [parent]
            for target in reversed(targets):
                target.terminate()
            _, alive = psutil.wait_procs(targets, timeout=12)
            for target in alive:
                target.kill()
        except psutil.NoSuchProcess:
            pass
        finally:
            self._process = None
            self._engine = None
            if self._log_handle:
                self._log_handle.close()
                self._log_handle = None
            PID_FILE.unlink(missing_ok=True)

    def _owns_live_process(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _adopt_pid_file(self) -> None:
        if not PID_FILE.exists():
            return
        try:
            data = json.loads(PID_FILE.read_text(encoding="utf-8"))
            engine = data["engine"]
            process = psutil.Process(int(data["pid"]))
            if engine in ("tts", "music") and _is_expected_process(process, engine):
                self._process = _ProcessAdapter(process.pid)
                self._engine = engine
                return
        except (OSError, ValueError, KeyError, json.JSONDecodeError, psutil.Error):
            pass
        PID_FILE.unlink(missing_ok=True)

    @staticmethod
    def _tail_log(engine: EngineName) -> str:
        path = LOG_ROOT / f"{engine}.log"
        if not path.exists():
            return "模型进程意外退出。"
        tail = path.read_text(encoding="utf-8", errors="replace")[-1800:]
        return f"模型启动失败：\n{tail}"


class _ProcessAdapter:
    """Small Popen-compatible adapter for a safely adopted persisted PID."""

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        """Return None while the adopted process still exists."""
        return None if psutil.pid_exists(self.pid) else 0


def _is_ready(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/gradio_api/info", timeout=1.2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _is_expected_process(process: psutil.Process, engine: EngineName | None) -> bool:
    try:
        joined = " ".join(process.cmdline()).lower()
        children = " ".join(
            " ".join(child.cmdline()) for child in process.children(recursive=True)
        ).lower()
    except psutil.Error:
        return False
    haystack = f"{joined} {children}"
    if engine == "tts":
        return "start-webui.bat" in haystack or "webui.py" in haystack
    if engine == "music":
        return "start-music.bat" in haystack or "acestep" in haystack
    return False

