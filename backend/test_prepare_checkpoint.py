"""Verify Windows resharding preserves every tensor byte and metadata field."""

import json
import struct

import pytest

from scripts.prepare_breeze_checkpoint import prepare_checkpoint, read_header


def _write_tensor_file(path, tensors):
    header = {"__metadata__": {"format": "pt"}}
    body = b""
    for name, data in tensors.items():
        header[name] = {"dtype": "U8", "shape": [len(data)], "data_offsets": [len(body), len(body) + len(data)]}
        body += data
    encoded = json.dumps(header).encode()
    encoded += b" " * (-len(encoded) % 8)
    path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + body)


def test_resharding_preserves_tensors_and_reuses_complete_cache(tmp_path):
    tensors = {"small": b"abc", "large": b"0123456789", "medium": b"hello"}
    original = tmp_path / "model.safetensors"
    _write_tensor_file(original, tensors)
    (tmp_path / "config.json").write_text('{"model_type":"breeze"}')
    audio = tmp_path / "audio_tokenizer"
    audio.mkdir()
    (audio / "config.json").write_text('{}')
    target = prepare_checkpoint(tmp_path, shard_bytes=8)
    index = json.loads((target / "model.safetensors.index.json").read_text())
    assert index["metadata"]["total_size"] == 18
    assert index["weight_map"]["large"].startswith("model-00001-")
    for name, expected in tensors.items():
        path = target / index["weight_map"][name]
        header, start = read_header(path)
        spec = header[name]
        assert spec["dtype"] == "U8"
        assert spec["shape"] == [len(expected)]
        assert path.read_bytes()[start + spec["data_offsets"][0]:start + spec["data_offsets"][1]] == expected
    assert (target / "config.json").read_bytes() == (tmp_path / "config.json").read_bytes()
    assert (target / "audio_tokenizer/config.json").is_file()
    before = (target / "prepared.json").stat().st_mtime_ns
    assert prepare_checkpoint(tmp_path, shard_bytes=8) == target
    assert (target / "prepared.json").stat().st_mtime_ns == before


def test_missing_prepared_shard_is_rebuilt(tmp_path):
    _write_tensor_file(tmp_path / "model.safetensors", {"weight": b"test"})
    target = prepare_checkpoint(tmp_path, shard_bytes=8)
    shard = next(target.glob("*.safetensors"))
    shard.unlink()
    prepare_checkpoint(tmp_path, shard_bytes=8)
    assert shard.is_file()


def test_checkpoint_index_cannot_escape_model_directory(tmp_path):
    (tmp_path / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"weight": "../outside.safetensors"}}))
    with pytest.raises(ValueError, match="Invalid checkpoint"):
        prepare_checkpoint(tmp_path)
