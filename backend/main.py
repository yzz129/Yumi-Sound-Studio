"""FastAPI entry point for the unified local audio studio."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

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
    reference: UploadFile = File(...),
    emotion_reference: UploadFile | None = File(None),
    text: str = Form(...),
    speed: float = Form(1.0),
    emotion: float = Form(0.65),
    language: str = Form("ZH"),
    emotion_mode: str = Form("voice"),
    emotion_vector: str = Form("[0,0,0,0,0,0,0,0]"),
    do_sample: bool = Form(True),
    top_p: float = Form(0.8),
    top_k: int = Form(30),
    temperature: float = Form(0.8),
    num_beams: int = Form(3),
    repetition_penalty: float = Form(10.0),
    segment_tokens: int = Form(120),
) -> dict[str, object]:
    """Queue a voice cloning request."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="请输入要说的话")
    source = await _save_upload(reference, "voice")
    emotion_source = await _save_upload(emotion_reference, "emotion") if emotion_reference else None
    if emotion_mode == "reference" and emotion_source is None:
        raise HTTPException(status_code=400, detail="请上传情绪参考声音")
    options = TtsOptions(
        language=language if language in {"ZH", "EN", "JA", "AR", "ES"} else "ZH",
        speed=_clamp(speed, 0.65, 1.6), emotion_mode=emotion_mode,
        emotion=_clamp(emotion, 0.0, 1.0), emotion_reference=emotion_source,
        emotion_vector=_parse_emotion_vector(emotion_vector), do_sample=do_sample,
        top_p=_clamp(top_p, 0.0, 1.0), top_k=max(0, min(100, top_k)),
        temperature=_clamp(temperature, 0.1, 2.0), num_beams=max(1, min(10, num_beams)),
        repetition_penalty=_clamp(repetition_penalty, 0.1, 20.0),
        segment_tokens=max(40, min(240, segment_tokens)),
    )

    def task(update):
        update("正在加载配音引擎，首次约需 1 分钟…")
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


def _parse_emotion_vector(value: str) -> list[float]:
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list) or len(parsed) != 8:
            raise ValueError
        return [_clamp(float(item), 0.0, 1.0) for item in parsed]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="情绪向量格式不正确") from exc


frontend = PROJECT_ROOT / "frontend" / "dist"
if frontend.exists():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """Serve the built React shell for non-API routes."""
        return FileResponse(frontend / "index.html")
