"""Phase 3 Notebook 运行时上下文与 prompt 构造。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any


SYSTEM_PROMPT = (
    "你是采购审核异常说明助手。只能引用用户提供的 input_facts、mismatches 和 evidence。"
    "不得计算、推断或补全未知 PO、GRN、发票号、金额、供应商、政策、审批人或异常类型。"
    "字段为 null 或缺失时，必须写“未提供”或“缺失”，不得根据其他单号补全。"
    "不得改变 risk_level，不得改变 recommended_action。"
    "输出必须严格使用这些章节：异常类型、事实边界、关键事实、缺失字段、禁止补全、审核结论。"
)


@dataclass(frozen=True)
class TrainingConfig:
    """LoRA SFT 的固定训练参数。"""

    seed: int = 42
    max_seq_length: int = 1024
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8
    num_train_epochs: int = 3
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    logging_steps: int = 5
    eval_strategy: str = "epoch"
    save_strategy: str = "epoch"
    load_best_model_at_end: bool = True


@dataclass(frozen=True)
class LoraConfigSpec:
    """LoRA adapter 的固定参数。"""

    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    bias: str = "none"
    target_modules: tuple[str, ...] = (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    )


@dataclass(frozen=True)
class GenerationConfig:
    """base/fine-tuned 对比推理参数。"""

    max_new_tokens: int = 256
    do_sample: bool = False


@dataclass(frozen=True)
class RuntimeContext:
    """Notebook 当前 Kernel 内可复用的训练上下文。"""

    project_root: Path
    model_id: str
    backend: str
    train_rows: list[dict[str, Any]]
    validation_rows: list[dict[str, Any]]
    test_rows: list[dict[str, Any]]
    training_config: TrainingConfig
    lora_config: LoraConfigSpec
    generation_config: GenerationConfig


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 UTF-8 JSONL。"""

    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def to_messages(row: dict[str, Any], include_answer: bool = True) -> list[dict[str, str]]:
    """把 Phase 3 样本转成 Qwen chat template messages。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                row["input_facts"], ensure_ascii=False, sort_keys=True
            ),
        },
    ]
    if include_answer:
        messages.append({"role": "assistant", "content": row["expected_explanation"]})
    return messages


def format_sft_row(tokenizer: Any, row: dict[str, Any]) -> dict[str, str]:
    """使用 tokenizer 的 chat template 生成 SFT 文本。"""

    return {"text": tokenizer.apply_chat_template(to_messages(row), tokenize=False)}


def write_predictions_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
    explanations: list[str],
) -> None:
    """写入 sample_id/explanation 格式的预测 JSONL。"""

    if len(rows) != len(explanations):
        raise ValueError("rows 与 explanations 数量不一致")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row, explanation in zip(rows, explanations):
            handle.write(
                json.dumps(
                    {"sample_id": row["sample_id"], "explanation": explanation},
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_artifacts_manifest(
    output_path: Path,
    artifact_paths: dict[str, Path],
    adapter_dir: Path | None = None,
) -> dict[str, Any]:
    """导出 Phase 3 训练产物清单，避免误把大文件提交到 Git。"""

    manifest: dict[str, Any] = {"files": {}, "adapter_dir": None}
    for name, path in artifact_paths.items():
        exists = path.exists()
        manifest["files"][name] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": path.stat().st_size if exists and path.is_file() else None,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            if exists and path.is_file()
            else None,
        }
    if adapter_dir is not None:
        files = sorted(item for item in adapter_dir.rglob("*") if item.is_file())
        manifest["adapter_dir"] = {
            "path": str(adapter_dir),
            "exists": adapter_dir.exists(),
            "file_count": len(files),
            "size_bytes": sum(item.stat().st_size for item in files),
            "files": [str(item.relative_to(adapter_dir)) for item in files],
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def build_runtime_context(
    project_root: Path,
    backend: str,
    model_id: str = "Qwen/Qwen2.5-0.5B-Instruct",
    seed: int = 42,
) -> RuntimeContext:
    """恢复 Notebook 当前 Kernel 需要的 Phase 3 训练上下文。"""

    data_dir = project_root / "data" / "phase3" / "generated"
    train_rows = read_jsonl(data_dir / "train.jsonl")
    validation_rows = read_jsonl(data_dir / "validation.jsonl")
    test_rows = read_jsonl(data_dir / "test.jsonl")
    if (len(train_rows), len(validation_rows), len(test_rows)) != (160, 20, 20):
        raise RuntimeError("Phase 3 数据拆分不是固定的 160/20/20")
    random.seed(seed)
    return RuntimeContext(
        project_root=project_root,
        model_id=model_id,
        backend=backend,
        train_rows=train_rows,
        validation_rows=validation_rows,
        test_rows=test_rows,
        training_config=TrainingConfig(seed=seed),
        lora_config=LoraConfigSpec(),
        generation_config=GenerationConfig(),
    )


def runtime_config_dict(context: RuntimeContext) -> dict[str, Any]:
    """导出可写入日志的 runtime 配置。"""

    return {
        "model_id": context.model_id,
        "backend": context.backend,
        "training": asdict(context.training_config),
        "lora": asdict(context.lora_config),
        "generation": asdict(context.generation_config),
        "sample_counts": {
            "train": len(context.train_rows),
            "validation": len(context.validation_rows),
            "test": len(context.test_rows),
        },
    }
