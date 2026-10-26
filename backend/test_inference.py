"""Breeze speech streaming and ACE-Step output compatibility tests."""

from pathlib import Path
import wave

import httpx
import pytest

from backend import inference
from backend.inference import (
    MusicOptions,
    TtsOptions,
    _configure_music_args,
    _extract_path,
    _tts_form,
    generate_tts,
)


def test_extracts_legacy_file_payload() -> None:
    assert _extract_path({"path": "C:/tmp/voice.wav"}) == "C:/tmp/voice.wav"


def test_extracts_new_gradio_update_payload() -> None:
    payload = {"playback_position": 0, "value": "C:/tmp/music.wav", "__type__": "update"}
    assert _extract_path(payload) == "C:/tmp/music.wav"


def test_extracts_first_available_nested_result() -> None:
    payload = [None, {"value": {"path": Path("C:/tmp/result.wav")}}]
    assert _extract_path(payload) == str(Path("C:/tmp/result.wav"))


def test_clone_uses_reference_transcript_without_direction(tmp_path: Path) -> None:
    reference = tmp_path / "voice.wav"
    data = _tts_form(reference, " 测试 ", TtsOptions(ref_text=" 参考文字 ", instruction="stale", seed=42))
    assert data == {"text": "测试", "ref_text": "参考文字", "cfg_scale": "1.0", "seed": "42"}


def test_design_omits_stale_reference(tmp_path: Path) -> None:
    data = _tts_form(tmp_path / "unused.wav", "你好", TtsOptions(
        mode="design", instruction="温柔的女声", ref_text="不应发送", seed=5,
    ))
    assert data == {"text": "你好", "instruction": "温柔的女声", "cfg_scale": "4.0", "seed": "5"}


def test_direction_combines_reference_and_instruction(tmp_path: Path) -> None:
    data = _tts_form(tmp_path / "voice.wav", "你好", TtsOptions(
        mode="direction", ref_text="参考", instruction="Speak slowly.", cfg_scale=3.5, seed=0,
    ))
    assert data["instruction"] == "Speak slowly."
    assert data["ref_text"] == "参考"
    assert data["cfg_scale"] == "3.5"
    assert data["seed"] == "0"


@pytest.mark.parametrize("reference, options", [
    (None, TtsOptions(ref_text="参考")),
    (Path("voice.wav"), TtsOptions()),
    (None, TtsOptions(mode="design")),
    (Path("voice.wav"), TtsOptions(mode="direction", ref_text="参考")),
    (None, TtsOptions(mode="unknown")),
])
def test_incomplete_speech_requests_are_rejected(reference, options) -> None:
    with pytest.raises(ValueError):
        _tts_form(reference, "测试", options)


def _mock_breeze(monkeypatch, tmp_path, response):
    original_client = httpx.Client
    requests = []

    def handle(request):
        request.read()
        requests.append(request)
        return response

    monkeypatch.setattr(inference, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(inference.httpx, "Client", lambda **kwargs: original_client(
        **kwargs, transport=httpx.MockTransport(handle),
    ))
    return requests


def test_breeze_pcm_becomes_playable_wav(monkeypatch, tmp_path: Path) -> None:
    pcm = b"\x00\x00\xff\x7f\x00\x80" * 24000
    requests = _mock_breeze(monkeypatch, tmp_path, httpx.Response(200, content=pcm, headers={
        "X-Sample-Format": "s16le", "X-Sample-Rate": "24000",
    }))
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"RIFF reference")
    target = generate_tts(reference, "你好", TtsOptions(ref_text="参考", seed=42))
    with wave.open(str(target), "rb") as audio:
        assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (24000, 1, 2)
        assert audio.readframes(audio.getnframes()) == pcm
    assert requests[0].url.path == "/v1/audio/speech"
    assert b'name="ref_audio"' in requests[0].content
    assert b"RIFF reference" in requests[0].content
    assert not list(tmp_path.glob("*.part"))


def test_design_sends_no_reference_file(monkeypatch, tmp_path: Path) -> None:
    requests = _mock_breeze(monkeypatch, tmp_path, httpx.Response(200, content=b"\0\0", headers={
        "X-Sample-Format": "s16le", "X-Sample-Rate": "24000",
    }))
    generate_tts(tmp_path / "missing-stale-file.wav", "你好", TtsOptions(mode="design", instruction="温柔"))
    assert b"ref_audio" not in requests[0].content
    assert b"ref_text" not in requests[0].content
    assert b"instruction" in requests[0].content


@pytest.mark.parametrize("pcm,headers", [
    (b"", {"X-Sample-Format": "s16le", "X-Sample-Rate": "24000"}),
    (b"\0", {"X-Sample-Format": "s16le", "X-Sample-Rate": "24000"}),
    (b"\0\0", {"X-Sample-Format": "f32", "X-Sample-Rate": "24000"}),
    (b"\0\0", {"X-Sample-Format": "s16le", "X-Sample-Rate": "0"}),
])
def test_invalid_audio_does_not_leave_outputs(monkeypatch, tmp_path: Path, pcm, headers) -> None:
    _mock_breeze(monkeypatch, tmp_path, httpx.Response(200, content=pcm, headers=headers))
    with pytest.raises(RuntimeError):
        generate_tts(None, "你好", TtsOptions(mode="design", instruction="温柔"))
    assert list(tmp_path.iterdir()) == []


def test_breeze_errors_are_reported(monkeypatch, tmp_path: Path) -> None:
    _mock_breeze(monkeypatch, tmp_path, httpx.Response(409, json={"detail": "already running"}))
    with pytest.raises(RuntimeError, match="already running"):
        generate_tts(None, "你好", TtsOptions(mode="design", instruction="温柔"))
    assert list(tmp_path.iterdir()) == []


def test_interrupted_stream_is_removed(monkeypatch, tmp_path: Path) -> None:
    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"\0\0" * 40000
            raise httpx.ReadError("stream disconnected")

    _mock_breeze(monkeypatch, tmp_path, httpx.Response(200, stream=BrokenStream(), headers={
        "X-Sample-Format": "s16le", "X-Sample-Rate": "24000",
    }))
    with pytest.raises(RuntimeError, match="音频流中断"):
        generate_tts(None, "你好", TtsOptions(mode="design", instruction="温柔"))
    assert list(tmp_path.iterdir()) == []


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
