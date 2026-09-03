"""Focused tests for Gradio output compatibility."""

from pathlib import Path

import pytest

from backend.inference import (
    MusicOptions,
    TtsOptions,
    _configure_music_args,
    _extract_path,
    _tts_arguments,
)


def test_extracts_legacy_file_payload() -> None:
    assert _extract_path({"path": "C:/tmp/voice.wav"}) == "C:/tmp/voice.wav"


def test_extracts_new_gradio_update_payload() -> None:
    payload = {"playback_position": 0, "value": "C:/tmp/music.wav", "__type__": "update"}
    assert _extract_path(payload) == "C:/tmp/music.wav"


def test_extracts_first_available_nested_result() -> None:
    payload = [None, {"value": {"path": Path("C:/tmp/result.wav")}}]
    assert _extract_path(payload) == "C:\\tmp\\result.wav"


def test_tts_speed_multiplier_is_converted_to_inverse_duration(tmp_path: Path) -> None:
    reference = tmp_path / "voice.wav"
    reference.write_bytes(b"RIFF")
    args = _tts_arguments(reference, "测试", TtsOptions(speed=1.25))
    assert args[17] == pytest.approx(0.8)


def test_music_advanced_options_map_to_gradio_contract(tmp_path: Path) -> None:
    source = tmp_path / "music.wav"
    source.write_bytes(b"RIFF")
    args = [None] * 72
    options = MusicOptions(
        edit_mode="flow_edit", preserve=0.94, melody_retention=0.22,
        inference_steps=14, batch_size=3, random_seed=False, seed="42",
        output_format="flac", normalize=True, fade_in=1.5, fade_out=2.0,
        source_caption="原曲", flow_min=0.1, flow_max=0.8, flow_samples=2,
    )
    _configure_music_args(args, source, "目标", options)
    assert args[6] == 14
    assert args[9] == "42"
    assert args[12] == 3
    assert args[18] == pytest.approx(0.94)
    assert args[19] == pytest.approx(0.22)
    assert args[35] == "flac"
    assert args[57:59] == [1.5, 2.0]
    assert args[65] is True
    assert args[66] == "原曲"
    assert args[68:71] == [0.1, 0.8, 2]
