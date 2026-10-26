"""Reshard safetensors using bounded byte copies for Windows model loading."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import sys
from contextlib import ExitStack
from pathlib import Path

SHARD_BYTES = 256 * 1024 * 1024
COPY_BYTES = 8 * 1024 * 1024


def read_header(path: Path) -> tuple[dict, int]:
    with path.open("rb") as source:
        size_bytes = source.read(8)
        if len(size_bytes) != 8:
            raise ValueError(f"Incomplete safetensors file: {path}")
        size = struct.unpack("<Q", size_bytes)[0]
        if size > 100 * 1024 * 1024 or size + 8 > path.stat().st_size:
            raise ValueError(f"Invalid safetensors header: {path}")
        header = json.loads(source.read(size))
    return header, size + 8


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def prepare_checkpoint(source: Path, shard_bytes: int = SHARD_BYTES) -> Path:
    """Keep identical tensor bytes, placing the largest tensors in early shards."""
    source = source.resolve()
    target = source / "windows"
    if not target.resolve().is_relative_to(source):
        raise ValueError("Prepared checkpoint must stay inside the source checkpoint")
    index_path = source / "model.safetensors.index.json"
    original_index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
    filenames = sorted(set(original_index["weight_map"].values())) if original_index else ["model.safetensors"]
    weight_files = []
    for name in filenames:
        path = source / name
        if not path.resolve().is_relative_to(source):
            raise ValueError(f"Invalid checkpoint file: {name}")
        weight_files.append(path)
    sidecars = [p for p in source.iterdir() if p.is_file() and p.suffix != ".safetensors" and p != index_path]
    audio_root = source / "audio_tokenizer"
    audio_files = [p for p in audio_root.rglob("*") if p.is_file()] if audio_root.is_dir() else []
    signature_data = {
        "version": 1, "shard_bytes": shard_bytes,
        "files": [(p.relative_to(source).as_posix(), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in sorted(weight_files + sidecars + audio_files + ([index_path] if original_index else []))],
    }
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    manifest_path = target / "prepared.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_signature") == signature and all(
            (target / name).is_file() and (target / name).stat().st_size == size
            for name, size in manifest.get("weights", {}).items()
        ) and (target / "model.safetensors.index.json").is_file():
            return target

    tensors = []
    for path in weight_files:
        header, data_start = read_header(path)
        data_size = path.stat().st_size - data_start
        for name, spec in header.items():
            if name == "__metadata__":
                continue
            start, end = spec["data_offsets"]
            if not 0 <= start <= end <= data_size:
                raise ValueError(f"Invalid tensor offsets: {name}")
            tensors.append((name, spec, path, data_start + start, end - start))
    names = [item[0] for item in tensors]
    if len(set(names)) != len(names) or (original_index and set(names) != set(original_index["weight_map"])):
        raise ValueError("Checkpoint tensor names do not match its index")
    tensors.sort(key=lambda item: (-item[4], item[0]))
    groups = []
    current = []
    size = 0
    for tensor in tensors:
        if current and size + tensor[4] > shard_bytes:
            groups.append(current)
            current, size = [], 0
        current.append(tensor)
        size += tensor[4]
    if current:
        groups.append(current)
    if not groups:
        raise ValueError("Checkpoint contains no tensors")
    target.mkdir(exist_ok=True)
    print(f"Preparing Windows checkpoint: {len(groups)} shards, unchanged tensor bytes", flush=True)
    weights = {}
    weight_map = {}
    with ExitStack() as stack:
        inputs = {path: stack.enter_context(path.open("rb")) for path in weight_files}
        for number, group in enumerate(groups, 1):
            filename = f"model-{number:05d}-of-{len(groups):05d}.safetensors"
            output = target / filename
            partial = output.with_suffix(".safetensors.part")
            header = {"__metadata__": {"format": "pt"}}
            offset = 0
            for name, spec, _, _, length in group:
                header[name] = {"dtype": spec["dtype"], "shape": spec["shape"], "data_offsets": [offset, offset + length]}
                offset += length
                weight_map[name] = filename
            encoded = json.dumps(header, separators=(",", ":")).encode()
            encoded += b" " * (-len(encoded) % 8)
            try:
                with partial.open("wb") as destination:
                    destination.write(struct.pack("<Q", len(encoded)))
                    destination.write(encoded)
                    for _, _, path, start, length in group:
                        source_file = inputs[path]
                        source_file.seek(start)
                        remaining = length
                        while remaining:
                            chunk = source_file.read(min(remaining, COPY_BYTES))
                            if not chunk:
                                raise ValueError(f"Incomplete checkpoint: {path}")
                            destination.write(chunk)
                            remaining -= len(chunk)
                partial.replace(output)
            finally:
                partial.unlink(missing_ok=True)
            weights[filename] = output.stat().st_size
            if number % 5 == 0 or number == len(groups):
                print(f"Prepared {number}/{len(groups)} shards", flush=True)
    for path in sidecars + audio_files:
        _link_or_copy(path, target / path.relative_to(source))
    index = {
        "metadata": {"total_size": sum(item[4] for item in tensors)},
        "weight_map": weight_map,
    }
    (target / "model.safetensors.index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps({"source_signature": signature, "weights": weights}, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(prepare_checkpoint(Path(sys.argv[1])))
