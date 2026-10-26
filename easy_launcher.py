"""Colab launcher for Easy-Irodori-TTS v1.2 (pinned upstream UI, public share link)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "Irodori-TTS"


def load_ui():
    import importlib.util
    source_file = REPO / "gradio_app_voicedesign.py"
    spec = importlib.util.spec_from_file_location("easy_irodori_upstream", source_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="依存関係とGPUの確認だけ行う")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--cpu", action="store_true", help="GPUがなくてもCPUで起動する")
    parser.add_argument("--no-share", action="store_true", help="公開リンクを作らない（通常は不要）")
    args = parser.parse_args()
    os.environ.setdefault("EASY_IRODORI_ROOT", str(ROOT))
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg が見つかりません。ノートブックのセットアップセルを実行してください。")
    sys.path.insert(0, str(REPO))
    internal = ROOT / "outputs" / "internal"
    internal.mkdir(parents=True, exist_ok=True)
    os.chdir(internal)
    import torch
    if not args.cpu and not torch.cuda.is_available():
        raise RuntimeError(
            "GPUが使えません。メニューの「ランタイム > ランタイムのタイプを変更」でGPUを選び、"
            "セッションを再起動してください。（CPUで動かす場合は --cpu）")
    if args.check:
        import torchaudio  # noqa: F401
        import torchcodec  # noqa: F401
        import soundfile  # noqa: F401
        load_ui()
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        print(f"Dependency check passed. PyTorch: {torch.__version__}; device: {gpu}")
        return
    ui = load_ui()
    from easy_ui import build_ui, CSS
    demo = build_ui(ui)
    demo.queue(default_concurrency_limit=1)
    demo.launch(
        server_name="0.0.0.0",
        server_port=args.port,
        share=not args.no_share,
        inbrowser=False,
        css=CSS,
    )


if __name__ == "__main__":
    main()
