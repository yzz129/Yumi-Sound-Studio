"""Run the official Breeze API with memory-conscious Windows weight loading."""

from __future__ import annotations

import os
import sys
from functools import wraps
from pathlib import Path


def use_pread(safetensors_module, device: str | None = None) -> None:
    """Read individual tensors without reserving Windows copy-on-write mappings."""
    original = safetensors_module.safe_open

    @wraps(original)
    def safe_open(*args, **kwargs):
        kwargs.setdefault("backend", "pread")
        framework = kwargs.get("framework", args[1] if len(args) > 1 else None)
        if device is not None and framework == "pt" and len(args) < 3:
            kwargs.setdefault("device", device)
        return original(*args, **kwargs)

    safetensors_module.safe_open = safe_open


def use_direct_device_loading(model_class, device: str) -> None:
    """Avoid staging the entire Breeze checkpoint in CPU RAM before GPU transfer."""
    original = model_class.from_pretrained

    @classmethod
    @wraps(original)
    def from_pretrained(cls, *args, **kwargs):
        kwargs.setdefault("device_map", device)
        return original(*args, **kwargs)

    model_class.from_pretrained = from_pretrained


def skip_allocator_warmup(modeling_utils) -> None:
    """Let tensors allocate incrementally instead of reserving the whole model."""
    modeling_utils.caching_allocator_warmup = lambda *args, **kwargs: None


def main() -> None:
    # EngineManager sets cwd to the separate, pinned upstream source directory.
    sys.path.insert(0, str(Path.cwd()))
    if os.name == "nt":
        from prepare_breeze_checkpoint import prepare_checkpoint

        sys.argv[1] = str(prepare_checkpoint(Path(sys.argv[1])))
        import safetensors
        import torch

        # Apply before importing Transformers, which binds safe_open at import time.
        device = f"cuda:{os.environ.get('LOCAL_RANK', '0')}" if torch.cuda.is_available() else "cpu"
        use_pread(safetensors, device)
        from breeze_infer.runtime import resolve_device
        from models.breeze import BreezeForConditionalGeneration
        from transformers import modeling_utils

        use_direct_device_loading(BreezeForConditionalGeneration, resolve_device())
        skip_allocator_warmup(modeling_utils)
        print("Breeze Windows loader: pread tensors, direct device placement", flush=True)
    from breeze_infer.api import main as serve

    serve()


if __name__ == "__main__":
    main()
