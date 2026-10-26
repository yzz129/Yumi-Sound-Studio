"""FastAPI entry point for the unified local audio studio."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import OUTPUT_ROOT, PROJECT_ROOT, UPLOAD_ROOT
from .engine_manager import EngineManager
from .inference import MusicOptions, TtsOptions, generate_music, generate_tts
from .jobs import JobQueue

app = FastAPI(title="音芽工作室", version="0.1.0")
engines = EngineManager()
jobs = JobQueue()


@app.get("/api/status")
def get_status() -> dict[str, object]:
    """Return local model availability."""
    return engines.status()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    """Return one asynchronous generation job."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@app.get("/api/outputs/{filename}")
def get_output(filename: str) -> FileResponse:
    """Serve a generated audio file from the controlled output directory."""
    safe_name = Path(filename).name
    path = OUTPUT_ROOT / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="音频不存在")
    return FileResponse(path, filename=safe_name)


@app.post("/api/tts")
async def create_tts(
    text: str = Form(...),
    reference: UploadFile | None = File(None),
    mode: Literal["clone", "design", "direction"] = Form("clone"),
    ref_text: str = Form(""),
    instruction: str = Form(""),
    cfg_scale: float = Form(4.0, ge=1.0, le=10.0),
    seed: int = Form(-1, ge=-1, le=4294967295),
) -> dict[str, object]:
    """Queue Breeze voice cloning, voice design, or voice direction."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="请输入要说的话")
    if mode != "design" and (reference is None or not reference.filename or not ref_text.strip()):
        raise HTTPException(status_code=400, detail="声音克隆需要参考音频和对应的准确文字稿")
    if mode != "clone" and not instruction.strip():
        raise HTTPException(status_code=400, detail="请描述想要的音色、情绪或说话方式")
    source = await _save_upload(reference, "voice") if mode != "design" and reference else None
    options = TtsOptions(
        mode=mode, ref_text=ref_text.strip() if source else "",
        instruction=instruction.strip() if mode != "clone" else "",
        cfg_scale=cfg_scale, seed=seed,
    )

    def task(update):
        update("正在加载 Breeze TTS 2，首次约需 1–2 分钟…")
        engines.ensure("tts")
        update("正在生成配音…")
        output = generate_tts(source, text.strip(), options)
        return f"/api/outputs/{output.name}"

    return jobs.submit("tts", task).__dict__


@app.post("/api/music")
async def create_music(
    source: UploadFile = File(...),
    caption: str = Form(...),
    preserve: float = Form(0.86),
    duration: int = Form(-1),
    edit_mode: str = Form("remix"),
    melody_retention: float = Form(0.2),
    inference_steps: int = Form(8),
    batch_size: int = Form(1),
    random_seed: bool = Form(True),
    seed: str = Form("-1"),
    lyrics: str = Form("[Instrumental]"),
    bpm: str = Form(""),
    key_scale: str = Form(""),
    time_signature: str = Form(""),
    output_format: str = Form("wav"),
    normalize: bool = Form(True),
    target_peak: float = Form(-1.0),
    fade_in: float = Form(0.0),
    fade_out: float = Form(0.0),
    repaint_start: float = Form(0.0),
    repaint_end: float = Form(-1.0),
    repaint_mode: str = Form("balanced"),
    repaint_strength: float = Form(0.5),
    source_caption: str = Form(""),
    flow_min: float = Form(0.0),
    flow_max: float = Form(1.0),
    flow_samples: int = Form(1),
    no_fsq: bool = Form(False),
    negative_prompt: str = Form(""),
) -> dict[str, object]:
    """Queue an instrumental source-audio remix request."""
    if not caption.strip():
        raise HTTPException(status_code=400, detail="请描述想怎么改")
    uploaded = await _save_upload(source, "music")
    if edit_mode not in {"remix", "flow_edit", "repaint"}:
        raise HTTPException(status_code=400, detail="不支持的音乐编辑方式")
    if edit_mode == "repaint" and repaint_end >= 0 and repaint_end <= repaint_start:
        raise HTTPException(status_code=400, detail="局部重绘结束时间需要晚于开始时间")
    options = MusicOptions(
        edit_mode=edit_mode, preserve=_clamp(preserve, 0.0, 1.0),
        melody_retention=_clamp(melody_retention, 0.0, 1.0), duration=duration,
        inference_steps=max(4, min(20, inference_steps)), batch_size=max(1, min(4, batch_size)),
        random_seed=random_seed, seed=seed, lyrics=lyrics,
        bpm=_optional_float(bpm), key_scale=key_scale.strip(), time_signature=time_signature.strip(),
        output_format=output_format, normalize=normalize, target_peak=_clamp(target_peak, -10.0, 0.0),
        fade_in=_clamp(fade_in, 0.0, 10.0), fade_out=_clamp(fade_out, 0.0, 10.0),
        repaint_start=max(0.0, repaint_start), repaint_end=repaint_end,
        repaint_mode=repaint_mode, repaint_strength=_clamp(repaint_strength, 0.0, 1.0),
        source_caption=source_caption, flow_min=_clamp(flow_min, 0.0, 1.0),
        flow_max=_clamp(flow_max, 0.0, 1.0), flow_samples=max(1, min(4, flow_samples)),
        no_fsq=no_fsq, negative_prompt=negative_prompt,
    )

    def task(update):
        update("正在加载音乐引擎，首次约需 1–2 分钟…")
        engines.ensure("music")
        update("正在保留原节奏并加入新元素…")
        outputs = generate_music(uploaded, caption.strip(), options)
        return [f"/api/outputs/{output.name}" for output in outputs]

    return jobs.submit("music", task).__dict__


async def _save_upload(upload: UploadFile, prefix: str) -> Path:
    suffix = Path(upload.filename or "audio.wav").suffix.lower()
    if prefix == "voice" and suffix not in {".wav", ".mp3", ".flac", ".ogg"}:
        raise HTTPException(status_code=400, detail="Breeze 参考声音支持 WAV、MP3、FLAC、OGG 格式")
    if suffix not in {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}:
        raise HTTPException(status_code=400, detail="请上传常见音频格式")
    target = UPLOAD_ROOT / f"{prefix}-{uuid.uuid4().hex}{suffix}"
    with target.open("wb") as destination:
        shutil.copyfileobj(upload.file, destination)
    return target


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _optional_float(value: str) -> float | None:
    if not value.strip():
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="BPM 必须是数字") from exc


frontend = PROJECT_ROOT / "frontend" / "dist"
if frontend.exists():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """Serve the built React shell for non-API routes."""
        return FileResponse(frontend / "index.html")
