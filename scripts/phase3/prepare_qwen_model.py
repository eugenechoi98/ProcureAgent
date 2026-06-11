"""Phase 3C：显式准备或验证 Qwen2.5-0.5B-Instruct 本地模型目录。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.gpu_notebook import (  # noqa: E402
    DEFAULT_MODEL_ID,
    assert_project_dependencies,
    model_dir_guard,
)


DEFAULT_MODELSCOPE_MODEL_DIR = Path(
    "/mnt/workspace/models/phase3/Qwen2.5-0.5B-Instruct"
)


def offline_upload_instructions(model_dir: Path) -> list[str]:
    """返回网络不可用时的离线上传说明。"""

    return [
        "Download the full Qwen/Qwen2.5-0.5B-Instruct model directory on a machine with network access.",
        "Confirm it contains config.json, tokenizer_config.json, tokenizer files, and safetensors weights.",
        f"Upload the complete directory to ModelScope: {model_dir}",
        "A zip/tar archive is also fine; extract it so model files are directly under that directory.",
        "After upload, rerun prepare_qwen_model.py --verify-only --model-dir with the same directory.",
    ]


def download_model(model_id: str, model_dir: Path) -> dict[str, Any]:
    """显式下载模型；只有 --download 会调用。"""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Missing huggingface_hub; install requirements/phase3-lora.txt in .venv-phase3 first."
        ) from exc

    model_dir.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_download(
        repo_id=model_id,
        local_dir=str(model_dir),
        allow_patterns=[
            "config.json",
            "generation_config.json",
            "tokenizer.json",
            "tokenizer.model",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "*.safetensors",
            "model.safetensors.index.json",
        ],
    )
    return {"downloaded_to": snapshot_path}


def main() -> None:
    """默认 dry-run；显式 --download 才下载。"""

    parser = ArgumentParser()
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODELSCOPE_MODEL_DIR)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    model_dir = args.model_dir.expanduser().resolve()
    result: dict[str, Any] = {
        "model_id": args.model_id,
        "model_dir": str(model_dir),
        "download_requested": args.download,
        "verify_only": args.verify_only,
        "offline_upload_instructions": offline_upload_instructions(model_dir),
    }
    result["project_dependencies"] = assert_project_dependencies()

    if args.download:
        try:
            result["download"] = download_model(args.model_id, model_dir)
        except Exception as exc:  # noqa: BLE001
            result["download_error"] = str(exc)
            result["message"] = (
                "Model download failed. If cloud network is unavailable, "
                "follow offline_upload_instructions and upload the full model directory."
            )
    elif not args.verify_only:
        result["message"] = "dry-run only; add --download to download or --verify-only to only check local files."

    result["guard"] = model_dir_guard(model_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

    if args.verify_only and not result["guard"]["ready"]:
        raise SystemExit(1)
    if args.download and not result["guard"]["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
