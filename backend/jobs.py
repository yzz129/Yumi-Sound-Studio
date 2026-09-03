"""Single-worker background job queue for GPU generation."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Callable

from loguru import logger


@dataclass
class Job:
    """Serializable state for one generation request."""

    id: str
    kind: str
    state: str = "queued"
    message: str = "已加入队列"
    result_url: str | None = None
    result_urls: list[str] | None = None
    error: str | None = None


class JobQueue:
    """Run one GPU job at a time and expose polling-friendly state."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, task: Callable[[Callable[[str], None]], str | list[str]]) -> Job:
        """Create a queued job and execute it asynchronously."""
        job = Job(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id, task)
        return job

    def get(self, job_id: str) -> dict[str, object] | None:
        """Return a snapshot for a known job."""
        with self._lock:
            job = self._jobs.get(job_id)
            return asdict(job) if job else None

    def _run(self, job_id: str, task: Callable[[Callable[[str], None]], str | list[str]]) -> None:
        self._update(job_id, state="running", message="正在准备模型…")
        try:
            result = task(lambda message: self._update(job_id, message=message))
            result_urls = result if isinstance(result, list) else [result]
            self._update(
                job_id,
                state="completed",
                message="生成完成",
                result_url=result_urls[0] if result_urls else None,
                result_urls=result_urls,
            )
        except Exception as exc:  # noqa: BLE001 - boundary converts failure to job state
            logger.exception("Generation job {} failed", job_id)
            self._update(job_id, state="failed", message="生成失败", error=str(exc))

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
