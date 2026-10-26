"""Breeze TTS 2 streaming and ACE-Step Gradio API adapters."""

from __future__ import annotations

import mimetypes
import secrets
import shutil
import time
import urllib.request
import uuid
import wave
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from gradio_client import Client, handle_file

from .config import MUSIC_URL, OUTPUT_ROOT, TTS_URL


@dataclass(frozen=True)
class TtsOptions:
    """Controls supported by the upstream Breeze TTS 2 speech API."""

    mode: str = "clone"
    ref_text: str = ""
    instruction: str = ""
    cfg_scale: float = 4.0
    seed: int = -1


@dataclass(frozen=True)
class MusicOptions:
    """Curated ACE-Step controls exposed by the unified studio."""

    edit_mode: str = "remix"
    preserve: float = 0.9
    melody_retention: float = 0.2
    duration: int = -1
    inference_steps: int = 8
    batch_size: int = 1
    random_seed: bool = True
    seed: str = "-1"
    lyrics: str = "[Instrumental]"
    bpm: float | None = None
    key_scale: str = ""
    time_signature: str = ""
    output_format: str = "wav"
    normalize: bool = True
    target_peak: float = -1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    repaint_start: float = 0.0
    repaint_end: float = -1.0
    repaint_mode: str = "balanced"
    repaint_strength: float = 0.5
    source_caption: str = ""
    flow_min: float = 0.0
    flow_max: float = 1.0
    flow_samples: int = 1
    no_fsq: bool = False
    negative_prompt: str = ""


def generate_tts(reference: Path | None, text: str, options: TtsOptions) -> Path:
    """Stream mono s16le PCM from Breeze into an atomic, playable WAV file."""
    data = _tts_form(reference, text, options)
    target = OUTPUT_ROOT / f"voice-{uuid.uuid4().hex}.wav"
    partial = target.with_suffix(".wav.part")
    try:
        with ExitStack() as stack:
            files = None
            if reference is not None and options.mode != "design":
                source = stack.enter_context(reference.open("rb"))
                mime = mimetypes.guess_type(reference.name)[0] or "application/octet-stream"
                files = {"ref_audio": (reference.name, source, mime)}
            client = stack.enter_context(httpx.Client(
                timeout=httpx.Timeout(900.0, connect=10.0, write=60.0), trust_env=False,
            ))
            response = stack.enter_context(client.stream(
                "POST", f"{TTS_URL}/v1/audio/speech", data=data, files=files,
            ))
            if response.is_error:
                response.read()
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise RuntimeError(f"Breeze TTS 2 生成失败（{response.status_code}）：{detail}")
            if response.headers.get("X-Sample-Format") != "s16le":
                raise RuntimeError("Breeze TTS 2 返回了不支持的音频格式。")
            sample_rate = int(response.headers.get("X-Sample-Rate", "0"))
            if not 8000 <= sample_rate <= 192000:
                raise RuntimeError("Breeze TTS 2 返回了无效的采样率。")
            size = 0
            with wave.open(str(partial), "wb") as destination:
                destination.setnchannels(1)
                destination.setsampwidth(2)
                destination.setframerate(sample_rate)
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(chunk) % 2:
                        raise RuntimeError("Breeze TTS 2 返回的音频流不完整，请重试。")
                    destination.writeframesraw(chunk)
                    size += len(chunk)
            if not size:
                raise RuntimeError("Breeze TTS 2 没有返回音频，请重试。")
        partial.replace(target)
        return target
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Breeze TTS 2 的连接或音频流中断，请查看 runtime/logs/tts.log。"
            "若内存或显存不足，请先关闭其他大型程序后重试。"
        ) from exc
    finally:
        partial.unlink(missing_ok=True)


def _tts_form(reference: Path | None, text: str, options: TtsOptions) -> dict[str, str]:
    if options.mode not in {"clone", "design", "direction"}:
        raise ValueError("不支持的配音方式")
    if not text.strip():
        raise ValueError("请输入要说的话")
    if options.mode != "design" and (reference is None or not options.ref_text.strip()):
        raise ValueError("声音克隆需要参考音频和对应的准确文字稿")
    if options.mode != "clone" and not options.instruction.strip():
        raise ValueError("请描述想要的音色、情绪或说话方式")
    data = {
        "text": text.strip(),
        "cfg_scale": str(1.0 if options.mode == "clone" else options.cfg_scale),
        "seed": str(secrets.randbelow(2**32) if options.seed == -1 else options.seed),
    }
    if options.mode != "design":
        data["ref_text"] = options.ref_text.strip()
    if options.mode != "clone":
        data["instruction"] = options.instruction.strip()
    return data


def generate_music(source: Path, caption: str, options: MusicOptions) -> list[Path]:
    """Remix or edit source audio using ACE-Step's supported generation controls."""
    client = Client(MUSIC_URL, verbose=False)
    mode = "Repaint" if options.edit_mode == "repaint" else "Remix"
    client.predict(mode, api_name="/_handle_mode_change")
    args = _music_defaults()
    _configure_music_args(args, source, caption, options)
    result = client.predict(*args, api_name="/generation_wrapper")
    return _collect_outputs(result, "music", options.batch_size)


def _configure_music_args(args: list[Any], source: Path, caption: str, options: MusicOptions) -> None:
    """Map curated settings to the current public Gradio API parameter order."""
    args[0] = caption
    args[1] = options.lyrics.strip() or "[Instrumental]"
    args[2] = options.bpm
    args[3] = options.key_scale
    args[4] = options.time_signature
    args[5] = "unknown"
    args[6] = max(4, min(20, options.inference_steps))
    args[8] = options.random_seed
    args[9] = "-1" if options.random_seed else options.seed
    args[10] = None
    args[11] = options.duration
    args[12] = max(1, min(4, options.batch_size))
    args[13] = handle_file(source)
    args[14] = None
    args[15] = max(0.0, options.repaint_start)
    args[16] = options.repaint_end
    args[18] = max(0.0, min(1.0, options.preserve))
    args[19] = max(0.0, min(1.0, options.melody_retention))
    args[20] = options.no_fsq
    args[24] = 3.0
    args[35] = options.output_format if options.output_format in {"wav", "flac", "mp3"} else "wav"
    args[39] = False
    args[43] = options.negative_prompt.strip() or "NO USER INPUT"
    args[48] = False
    args[49] = False
    args[50] = False
    args[55] = options.normalize
    args[56] = max(-10.0, min(0.0, options.target_peak))
    args[57] = max(0.0, min(10.0, options.fade_in))
    args[58] = max(0.0, min(10.0, options.fade_out))
    args[61] = options.repaint_mode if options.repaint_mode in {"conservative", "balanced", "aggressive"} else "balanced"
    args[62] = max(0.0, min(1.0, options.repaint_strength))
    args[63] = 0.0
    args[64] = ""
    args[65] = options.edit_mode == "flow_edit"
    args[66] = options.source_caption.strip() or "original source music"
    args[67] = options.lyrics.strip() or "[Instrumental]"
    args[68] = max(0.0, min(1.0, options.flow_min))
    args[69] = max(args[68], min(1.0, options.flow_max))
    args[70] = max(1, min(4, options.flow_samples))
    args[71] = False


def _music_defaults() -> list[Any]:
    with urllib.request.urlopen(f"{MUSIC_URL}/gradio_api/info", timeout=10) as response:
        import json

        data = json.load(response)
    parameters = data["named_endpoints"]["/generation_wrapper"]["parameters"]
    defaults = [item.get("parameter_default") for item in parameters]
    if len(defaults) < 72:
        raise RuntimeError("ACE-Step 接口版本过旧，缺少高级编辑参数。")
    return defaults


def _collect_outputs(result: Any, prefix: str, limit: int) -> list[Path]:
    items = list(result) if isinstance(result, (tuple, list)) else [result]
    outputs: list[Path] = []
    seen: set[str] = set()
    for item in items[:8]:
        candidate = _extract_path(item)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        source = Path(str(candidate))
        if source.exists():
            outputs.append(_copy_output(source, prefix, len(outputs)))
        if len(outputs) >= max(1, limit):
            break
    if not outputs:
        raise RuntimeError("模型没有返回音频文件。")
    return outputs


def _copy_output(source: Path, prefix: str, index: int) -> Path:
    suffix = source.suffix or ".wav"
    marker = f"-{index + 1}" if index else ""
    target = OUTPUT_ROOT / f"{prefix}-{int(time.time() * 1000)}{marker}{suffix}"
    shutil.copy2(source, target)
    return target


def _extract_path(value: Any) -> str | None:
    """Extract a file path from Gradio 4/5/6 file and update payloads."""
    if isinstance(value, (str, Path)):
        return str(value)
    if isinstance(value, dict):
        for key in ("path", "value"):
            candidate = _extract_path(value.get(key))
            if candidate:
                return candidate
    if isinstance(value, (tuple, list)):
        for item in value:
            candidate = _extract_path(item)
            if candidate:
                return candidate
    return None
