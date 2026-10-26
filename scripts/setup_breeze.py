"""Install the pinned Breeze TTS 2 runtime and its complete local checkpoint."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SOURCE_URL = "https://github.com/breezeblue-ai/breeze-tts.git"
SOURCE_REVISION = "6eba901d1845353802652c708a4740fdfc5baa75"
MODEL_ID = "BreezeBlue/breeze-tts-2"
MODEL_REVISION = "3e28c5151381a722f1d8661b4118c298caa77aa4"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    root = Path(os.environ.get("BREEZE_TTS_ROOT", PROJECT_ROOT.parent / "breeze-tts")).resolve()
    model = Path(os.environ.get("BREEZE_MODEL_DIR", root / "checkpoints" / "breeze-tts-2")).resolve()
    if not root.exists():
        subprocess.run(["git", "clone", "--no-checkout", "--depth", "1", SOURCE_URL, str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "fetch", "--depth", "1", "origin", SOURCE_REVISION], check=True)
        subprocess.run(["git", "-C", str(root), "checkout", "--detach", SOURCE_REVISION], check=True)
    if not (root / "breeze_infer" / "api.py").is_file():
        raise RuntimeError(f"Not a Breeze TTS source directory: {root}")
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision != SOURCE_REVISION:
        raise RuntimeError(f"Expected Breeze source {SOURCE_REVISION}, found {revision}. Check the source version first.")
    exclude = root / ".git" / "info" / "exclude"
    if exclude.parent.is_dir():
        existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        patterns = [pattern for pattern in ("/.venv/", "/checkpoints/") if pattern not in existing.splitlines()]
        if patterns:
            with exclude.open("a", encoding="utf-8") as destination:
                destination.write("\n" + "\n".join(patterns) + "\n")
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        subprocess.run(["uv", "venv", "--python", "3.11", str(root / ".venv")], check=True)
    subprocess.run([
        "uv", "pip", "install", "--python", str(python), "--torch-backend=cu128",
        "-r", str(root / "requirements.txt"), "safetensors==0.8.0",
    ], check=True)
    subprocess.run([
        str(python), "-c",
        "import sys; from huggingface_hub import snapshot_download; "
        "snapshot_download(repo_id=sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3], "
        "allow_patterns=['*.json', '*.safetensors', 'LICENSE'], max_workers=3)",
        MODEL_ID, MODEL_REVISION, str(model),
    ], check=True, cwd=root)
    if os.name == "nt":
        subprocess.run([
            str(python), str(PROJECT_ROOT / "scripts" / "prepare_breeze_checkpoint.py"), str(model),
        ], check=True)
    subprocess.run([
        str(python), "-c",
        "import torch; import breeze_infer.api; "
        "assert torch.cuda.is_available(), 'CUDA GPU is not available'; "
        "print('Breeze TTS 2 ready:', torch.cuda.get_device_name(0))",
    ], check=True, cwd=root)
    print(f"Model installed at {model}. Start the studio with start-studio.bat.")


if __name__ == "__main__":
    main()
