"""Exercise the studio's Breeze request contract without loading GPU models."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.jobs import Job


@pytest.fixture
def studio(monkeypatch, tmp_path):
    submissions = []

    def submit(kind, task):
        submissions.append(task)
        return Job(id="test-job", kind=kind)

    monkeypatch.setattr(main, "jobs", SimpleNamespace(submit=submit))
    monkeypatch.setattr(main, "UPLOAD_ROOT", tmp_path)
    return TestClient(main.app), submissions


@pytest.mark.parametrize("data,files", [
    ({"text": "你好"}, None),
    ({"text": "你好", "ref_text": "参考"}, None),
    ({"text": "你好"}, {"reference": ("voice.wav", b"RIFF", "audio/wav")}),
    ({"text": "你好", "mode": "design"}, None),
    ({"text": "  ", "mode": "design", "instruction": "温柔"}, None),
    ({"text": "你好", "mode": "direction", "ref_text": "参考"}, {"reference": ("voice.wav", b"RIFF", "audio/wav")}),
])
def test_invalid_requests_never_enter_gpu_queue(studio, data, files):
    client, submissions = studio
    response = client.post("/api/tts", data=data, files=files)
    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)
    assert not submissions


def test_design_without_upload_reaches_breeze(studio, monkeypatch, tmp_path):
    client, submissions = studio
    generated = []
    ensured = []
    monkeypatch.setattr(main, "engines", SimpleNamespace(ensure=ensured.append))

    def generate(reference, text, options):
        generated.append((reference, text, options))
        return tmp_path / "voice.wav"

    monkeypatch.setattr(main, "generate_tts", generate)
    response = client.post("/api/tts", data={
        "text": " 你好 ", "mode": "design", "instruction": " 温柔 ", "cfg_scale": 4, "seed": 42,
    })
    assert response.status_code == 200
    assert submissions[0](lambda message: None) == "/api/outputs/voice.wav"
    assert ensured == ["tts"]
    reference, text, options = generated[0]
    assert reference is None
    assert text == "你好"
    assert (options.mode, options.instruction, options.seed, options.cfg_scale) == ("design", "温柔", 42, 4)


def test_clone_upload_and_transcript_reach_breeze(studio, monkeypatch, tmp_path):
    client, submissions = studio
    generated = []
    monkeypatch.setattr(main, "engines", SimpleNamespace(ensure=lambda engine: None))
    monkeypatch.setattr(main, "generate_tts", lambda reference, text, options: (
        generated.append((reference, options)) or tmp_path / "voice.wav"
    ))
    response = client.post("/api/tts", data={"text": "你好", "ref_text": "参考", "instruction": "stale"},
                           files={"reference": ("voice.wav", b"RIFF reference", "audio/wav")})
    assert response.status_code == 200
    submissions[0](lambda message: None)
    reference, options = generated[0]
    assert reference.read_bytes() == b"RIFF reference"
    assert options.ref_text == "参考"
    assert options.instruction == ""


def test_reference_format_is_checked_before_loading_breeze(studio):
    client, submissions = studio
    response = client.post("/api/tts", data={"text": "你好", "ref_text": "参考"},
                           files={"reference": ("voice.m4a", b"audio", "audio/mp4")})
    assert response.status_code == 400
    assert "WAV" in response.json()["detail"]
    assert not submissions


@pytest.mark.parametrize("field,value", [("mode", "unknown"), ("cfg_scale", "nan"), ("cfg_scale", "0"), ("seed", "-2"), ("seed", "4294967296")])
def test_unsupported_breeze_parameters_are_rejected(studio, field, value):
    client, submissions = studio
    data = {"mode": "design", "text": "你好", "instruction": "温柔", field: value}
    assert client.post("/api/tts", data=data).status_code == 422
    assert not submissions
