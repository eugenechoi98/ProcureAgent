"""LayoutLMv3 GPU 训练配置、guard、日志和报告工具。"""

from dataclasses import asdict, dataclass
import csv
import json
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class LayoutLMv3TrainingConfig:
    """Phase 1E 保守训练参数。"""

    model_name: str = "microsoft/layoutlmv3-base"
    max_length: int = 512
    batch_size: int = 2
    gradient_accumulation_steps: int = 4
    epochs: int = 5
    learning_rate: float = 1e-5
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    seed: int = 42


@dataclass(frozen=True)
class TrainingGuardState:
    """训练开始前必须满足的状态。"""

    cuda_available: bool
    train_samples: int
    validation_samples: int
    labels_non_o_count: int
    baseline_report_exists: bool


@dataclass(frozen=True)
class EpochLog:
    """单个 epoch 的训练日志。"""

    epoch: int
    train_loss: float
    validation_loss: float
    token_f1: float
    field_macro_f1: float
    learning_rate: float
    elapsed_time: float


def validate_training_guard(state: TrainingGuardState) -> None:
    """检查 GPU、数据、实体标签和 baseline 报告。"""

    failures: list[str] = []
    if not state.cuda_available:
        failures.append("cuda_available must be true")
    if state.train_samples <= 0:
        failures.append("train_samples must be greater than zero")
    if state.validation_samples <= 0:
        failures.append("validation_samples must be greater than zero")
    if state.labels_non_o_count <= 0:
        failures.append("labels_non_o_count must be greater than zero")
    if not state.baseline_report_exists:
        failures.append("baseline_report_exists must be true")
    if failures:
        raise RuntimeError("Training guard failed: " + "; ".join(failures))


def select_best_epoch(logs: list[EpochLog]) -> EpochLog:
    """按 field macro F1 优先、validation loss 次优选择最佳 epoch。"""

    if not logs:
        raise ValueError("At least one epoch log is required.")
    return max(logs, key=lambda item: (item.field_macro_f1, -item.validation_loss))


def build_training_report(
    *,
    config: LayoutLMv3TrainingConfig,
    logs: list[EpochLog],
    baseline_macro_f1: float,
    data_source: str = "Voxel51/scanned_receipts",
    evaluation_split: str = "local_validation_split_seed_42",
) -> dict[str, Any]:
    """生成训练报告 JSON 结构。"""

    best = select_best_epoch(logs)
    return {
        "data_source": data_source,
        "evaluation_split": evaluation_split,
        "model_name": config.model_name,
        "seed": config.seed,
        "batch_size": config.batch_size,
        "gradient_accumulation_steps": config.gradient_accumulation_steps,
        "epochs": config.epochs,
        "learning_rate": config.learning_rate,
        "best_epoch": best.epoch,
        "baseline_macro_f1": baseline_macro_f1,
        "fine_tuned_macro_f1": best.field_macro_f1,
        "improvement": best.field_macro_f1 - baseline_macro_f1,
        "epoch_logs": [asdict(log) for log in logs],
    }


def write_training_outputs(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """保存 JSON、CSV 和 Markdown 训练摘要。"""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "layoutlmv3_training_report.json"
    csv_path = output / "layoutlmv3_training_log.csv"
    markdown_path = output / "layoutlmv3_training_report.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logs = report["epoch_logs"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EpochLog.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(logs)
    markdown_path.write_text(training_report_to_markdown(report), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path}


def training_report_to_markdown(report: dict[str, Any]) -> str:
    """生成简洁 Markdown 训练报告。"""

    lines = [
        "# LayoutLMv3 Training Report",
        "",
        f"- data_source: {report['data_source']}",
        f"- evaluation_split: {report['evaluation_split']}",
        f"- model_name: {report['model_name']}",
        f"- seed: {report['seed']}",
        f"- batch_size: {report['batch_size']}",
        f"- gradient_accumulation_steps: {report['gradient_accumulation_steps']}",
        f"- epochs: {report['epochs']}",
        f"- learning_rate: {report['learning_rate']}",
        f"- best_epoch: {report['best_epoch']}",
        f"- baseline_macro_f1: {report['baseline_macro_f1']:.4f}",
        f"- fine_tuned_macro_f1: {report['fine_tuned_macro_f1']:.4f}",
        f"- improvement: {report['improvement']:.4f}",
        "",
        "| epoch | train_loss | validation_loss | token_f1 | field_macro_f1 | learning_rate | elapsed_time |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for log in report["epoch_logs"]:
        lines.append(
            f"| {log['epoch']} | {log['train_loss']:.6f} | {log['validation_loss']:.6f} | "
            f"{log['token_f1']:.4f} | {log['field_macro_f1']:.4f} | "
            f"{log['learning_rate']:.8f} | {log['elapsed_time']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def save_loss_curve(
    logs: list[EpochLog],
    output_path: str | Path,
    plotter: Callable[..., Any] | None = None,
) -> Path:
    """保存 train/validation loss 曲线 PNG。"""

    if not logs:
        raise ValueError("At least one epoch log is required.")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if plotter is not None:
        plotter(logs, output)
        return output
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required to save the loss curve. Install extraction dependencies."
        ) from exc
    epochs = [log.epoch for log in logs]
    plt.figure(figsize=(7, 4))
    plt.plot(epochs, [log.train_loss for log in logs], marker="o", label="train")
    plt.plot(epochs, [log.validation_loss for log in logs], marker="o", label="validation")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("LayoutLMv3 Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output, dpi=160)
    plt.close()
    return output
