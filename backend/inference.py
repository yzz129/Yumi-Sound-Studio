"""Gradio API adapters for IndexTTS and ACE-Step."""

from __future__ import annotations

import shutil
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gradio_client import Client, handle_file

from .config import MUSIC_URL, OUTPUT_ROOT, TTS_URL


@dataclass(frozen=True)
class TtsOptions:
    """User-facing IndexTTS controls with safe local defaults."""

    language: str = "ZH"
    speed: float = 1.0
    emotion_mode: str = "voice"
    emotion: float = 0.65
    emotion_reference: Path | None = None
    emotion_vector: list[float] = field(default_factory=lambda: [0.0] * 8)
    do_sample: bool = True
    top_p: float = 0.8
    top_k: int = 30
    temperature: float = 0.8
    num_beams: int = 3
    repetition_penalty: float = 10.0
    segment_tokens: int = 120


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


def generate_tts(reference: Path, text: str, options: TtsOptions) -> Path:
    """Generate speech from one voice reference and copy it into app outputs."""
    client = Client(TTS_URL, verbose=False)
    args = _tts_arguments(reference, text, options)
    result = client.predict(*args, api_name="/gen_single")
    return _collect_output(result, "voice")


def _tts_arguments(reference: Path, text: str, options: TtsOptions) -> list[Any]:
    emotion_methods = {
        "voice": "与音色参考音频相同",
        "reference": "使用情感参考音频",
        "vector": "使用情感向量控制",
    }
    vector = [max(0.0, min(1.0, float(value))) for value in options.emotion_vector[:8]]
    vector.extend([0.0] * (8 - len(vector)))
    emotion_reference = handle_file(options.emotion_reference) if options.emotion_reference else None
    # IndexTTS duration_factor is inverse to the user-facing speed multiplier.
    duration_factor = 1.0 / max(0.2, options.speed)
    return [
        emotion_methods.get(options.emotion_mode, emotion_methods["voice"]),
        handle_file(reference),
        text,
        options.language,
        emotion_reference,
        max(0.0, min(1.0, options.emotion)),
        *vector,
        "",  # emotion text requires the optional Qwen emotion model
        False,
        max(40, min(240, options.segment_tokens)),
        duration_factor,
        options.do_sample,
        max(0.0, min(1.0, options.top_p)),
        max(0, min(100, options.top_k)),
        max(0.1, min(2.0, options.temperature)),
        0.0,
        max(1, min(10, options.num_beams)),
        max(0.1, min(20.0, options.repetition_penalty)),
        1500,
    ]


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


def _collect_output(result: Any, prefix: str) -> Path:
    candidate = _extract_path(result)
    if not candidate:
        raise RuntimeError("模型没有返回音频文件。")
    source = Path(str(candidate))
    if not source.exists():
        raise RuntimeError(f"模型输出不存在：{source}")
    return _copy_output(source, prefix, 0)


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
