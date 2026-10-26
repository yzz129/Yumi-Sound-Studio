"""Check that Windows loading overrides preserve upstream caller options."""

from types import SimpleNamespace

from scripts.breeze_server import skip_allocator_warmup, use_direct_device_loading, use_pread


def test_windows_reader_defaults_to_pread_and_preserves_explicit_backend():
    calls = []
    module = SimpleNamespace(safe_open=lambda *args, **kwargs: calls.append((args, kwargs)))
    use_pread(module)
    module.safe_open("weights.safetensors", framework="pt")
    module.safe_open("weights.safetensors", framework="pt", backend="mmap")
    assert calls[0] == (("weights.safetensors",), {"framework": "pt", "backend": "pread"})
    assert calls[1][1]["backend"] == "mmap"


def test_windows_model_loads_directly_on_device_and_preserves_explicit_map():
    calls = []

    class Model:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            calls.append((args, kwargs))
            return cls

    use_direct_device_loading(Model, "cuda:0")
    assert Model.from_pretrained("checkpoint", dtype="bfloat16") is Model
    Model.from_pretrained("checkpoint", device_map="cpu")
    assert calls[0] == (("checkpoint",), {"dtype": "bfloat16", "device_map": "cuda:0"})
    assert calls[1][1]["device_map"] == "cpu"


def test_windows_tensor_reader_uses_gpu_without_cpu_file_mapping():
    calls = []
    module = SimpleNamespace(safe_open=lambda *args, **kwargs: calls.append((args, kwargs)))
    use_pread(module, "cuda:0")
    module.safe_open("weights", framework="pt")
    module.safe_open("weights", framework="pt", device="cpu")
    module.safe_open("weights", "pt", "cpu")
    assert calls[0][1]["device"] == "cuda:0"
    assert calls[1][1]["device"] == "cpu"
    assert "device" not in calls[2][1]


def test_windows_loader_skips_large_allocator_reservation():
    calls = []
    module = SimpleNamespace(caching_allocator_warmup=lambda *args: calls.append(args))
    skip_allocator_warmup(module)
    assert module.caching_allocator_warmup("model", {"layer": "cuda:0"}, None) is None
    assert calls == []
