"""在当前 Notebook Kernel 内恢复完整 LayoutLMv3 训练上下文。"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from procureguard.extraction.alignment import ID2LABEL, LABEL2ID
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.gpu_notebook import (
    load_baseline_macro_f1,
    require_safetensors_model,
)
from procureguard.extraction.layoutlmv3_dataset import create_layoutlmv3_processor


GPU_NOTEBOOK_REQUIRED_NAMES = [
    "PROJECT_ROOT",
    "PROCESSED_DIR",
    "MODEL_DIR",
    "BASELINE_REPORT_PATH",
    "MODEL_NAME",
    "MAX_LENGTH",
    "BATCH_SIZE",
    "GRAD_ACCUMULATION_STEPS",
    "EPOCHS",
    "LEARNING_RATE",
    "WEIGHT_DECAY",
    "MAX_GRAD_NORM",
    "SEED",
    "BASELINE_MACRO_F1",
    "LABEL2ID",
    "ID2LABEL",
    "train_samples",
    "validation_samples",
    "processor",
    "torch",
    "device",
]


def build_gpu_notebook_context(
    *,
    project_root: str | Path,
    processed_dir: str | Path,
    model_dir: str | Path,
    baseline_report_path: str | Path,
    processor_factory: Callable[..., Any] = create_layoutlmv3_processor,
    torch_module: Any | None = None,
) -> dict[str, object]:
    """在当前 Kernel 加载真实样本、BIO 标签、本地 processor 和训练配置。"""

    root = Path(project_root).resolve()
    processed = Path(processed_dir).resolve()
    model = Path(model_dir).resolve()
    baseline_path = Path(baseline_report_path).resolve()
    train_path = processed / "train.jsonl"
    validation_path = processed / "validation.jsonl"

    if not (root / "pyproject.toml").is_file():
        raise FileNotFoundError(f"Invalid project root: {root}")
    require_safetensors_model(model)
    if not train_path.is_file() or not validation_path.is_file():
        raise FileNotFoundError(
            f"Processed train/validation JSONL is incomplete under: {processed}"
        )
    if not baseline_path.is_file():
        raise FileNotFoundError(f"Baseline report does not exist: {baseline_path}")

    torch = torch_module or importlib.import_module("torch")
    train_samples = read_processed_jsonl(train_path)
    validation_samples = read_processed_jsonl(validation_path)
    baseline_macro_f1 = load_baseline_macro_f1(baseline_path)
    if baseline_macro_f1 is None:
        raise ValueError(f"Baseline macro F1 is missing: {baseline_path}")
    processor = processor_factory(model, local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))

    return {
        "PROJECT_ROOT": root,
        "PROCESSED_DIR": processed,
        "MODEL_DIR": model,
        "BASELINE_REPORT_PATH": baseline_path,
        "MODEL_NAME": str(model),
        "MAX_LENGTH": 512,
        "BATCH_SIZE": 2,
        "GRAD_ACCUMULATION_STEPS": 4,
        "EPOCHS": 5,
        "LEARNING_RATE": 1e-5,
        "WEIGHT_DECAY": 0.01,
        "MAX_GRAD_NORM": 1.0,
        "SEED": 42,
        "BASELINE_MACRO_F1": baseline_macro_f1,
        "LABEL2ID": LABEL2ID,
        "ID2LABEL": ID2LABEL,
        "train_samples": train_samples,
        "validation_samples": validation_samples,
        "processor": processor,
        "torch": torch,
        "device": device,
        "baseline_report": baseline_report,
    }


def find_missing_runtime_names(
    namespace: Mapping[str, object],
    required_names: list[str] | None = None,
) -> list[str]:
    """一次性返回 Notebook 当前缺失的全部训练变量。"""

    names = required_names or GPU_NOTEBOOK_REQUIRED_NAMES
    return [name for name in names if name not in namespace]


def require_complete_runtime_context(
    namespace: Mapping[str, object],
    required_names: list[str] | None = None,
) -> list[str]:
    """preflight 检查完整上下文，缺失时一次性报出全部变量。"""

    missing_names = find_missing_runtime_names(namespace, required_names)
    if missing_names:
        raise RuntimeError(f"Notebook runtime context incomplete: {missing_names}")
    return missing_names
