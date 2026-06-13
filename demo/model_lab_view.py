"""Model Lab 只读展示层，读取已验收的轻量 artifacts。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_LAB_ROOT = PROJECT_ROOT / "demo" / "model_lab"


def load_model_lab_artifacts(root: Path = MODEL_LAB_ROOT) -> dict[str, Any]:
    """读取 Model Lab 所需的所有轻量 JSON。"""

    return {
        "manifest": _read_json(root / "manifest.json"),
        "layout_metrics": _read_json(root / "layoutlmv3" / "metrics.json"),
        "layout_curve": _read_json(root / "layoutlmv3" / "training_curve.json"),
        "layout_predictions": _read_json(
            root / "layoutlmv3" / "selected_predictions.json"
        ),
        "layout_errors": _read_json(root / "layoutlmv3" / "error_analysis.json"),
        "lora_metrics": _read_json(root / "lora" / "metrics.json"),
        "lora_curves": _read_json(root / "lora" / "training_curves.json"),
        "lora_hallucinations": _read_json(root / "lora" / "hallucination_cases.json"),
        "lora_guard_cases": _read_json(root / "lora" / "guard_cases.json"),
    }


def build_model_lab_tab(gr: Any, artifacts: dict[str, Any] | None = None) -> None:
    """构建 Model Lab 页签内容，不启动模型推理。"""

    data = artifacts or load_model_lab_artifacts()
    gr.Markdown(render_model_lab_summary(data), elem_id="model-lab-summary")
    gr.Dataframe(
        value=layout_metric_rows(data),
        row_count=len(layout_metric_rows(data)),
        headers=["metric", "value"],
        datatype=["str", "str"],
        label="LayoutLMv3 Metrics",
        interactive=False,
        elem_id="layoutlmv3-metrics-table",
    )
    gr.Dataframe(
        value=layout_field_f1_rows(data),
        row_count=len(layout_field_f1_rows(data)),
        headers=[
            "field",
            "OCR + Regex",
            "First LayoutLMv3",
            "Corrected LayoutLMv3",
        ],
        datatype=["str", "str", "str", "str"],
        label="LayoutLMv3 Field-level F1",
        interactive=False,
        elem_id="layoutlmv3-field-f1-table",
    )
    gr.Dataframe(
        value=layout_training_curve_rows(data),
        row_count=len(layout_training_curve_rows(data)),
        headers=["epoch", "train_loss", "validation_loss", "token_f1", "field_macro_f1"],
        datatype=["str", "str", "str", "str", "str"],
        label="LayoutLMv3 Training Curve",
        interactive=False,
        elem_id="layoutlmv3-training-curve-table",
    )
    gr.Dataframe(
        value=layout_prediction_rows(data),
        row_count=len(layout_prediction_rows(data)),
        headers=[
            "case_id",
            "ground_truth_date",
            "legacy_date",
            "cleaned_date",
            "error_attribution",
        ],
        datatype=["str", "str", "str", "str", "str"],
        label="Selected Checkpoint Predictions",
        interactive=False,
        elem_id="layoutlmv3-predictions-table",
    )
    gr.JSON(
        value=data["layout_errors"],
        label="LayoutLMv3 Error Analysis",
        elem_id="layoutlmv3-error-analysis-json",
    )
    gr.Markdown(render_lora_summary(data), elem_id="lora-summary")
    gr.Dataframe(
        value=lora_metric_rows(data),
        row_count=len(lora_metric_rows(data)),
        headers=["run", "variant", "metric", "value"],
        datatype=["str", "str", "str", "str"],
        label="LoRA Metrics",
        interactive=False,
        elem_id="lora-metrics-table",
    )
    gr.Dataframe(
        value=lora_training_curve_rows(data),
        row_count=len(lora_training_curve_rows(data)),
        headers=["run", "epoch", "train_loss", "validation_loss"],
        datatype=["str", "str", "str", "str"],
        label="LoRA Training Curves",
        interactive=False,
        elem_id="lora-training-curves-table",
    )
    gr.Dataframe(
        value=lora_hallucination_rows(data),
        row_count=len(lora_hallucination_rows(data)),
        headers=[
            "run_id",
            "sample_id",
            "hallucination_type",
            "unsupported_content",
            "source_file",
        ],
        datatype=["str", "str", "str", "str", "str"],
        label="LoRA Hallucination Cases",
        interactive=False,
        elem_id="lora-hallucination-cases-table",
    )
    gr.Dataframe(
        value=lora_guard_case_rows(data),
        row_count=len(lora_guard_case_rows(data)),
        headers=[
            "case_id",
            "source_type",
            "guard_passed",
            "fallback_reason",
            "final_source",
            "evidence_scope",
        ],
        datatype=["str", "str", "str", "str", "str", "str"],
        label="Guard And Fallback Cases",
        interactive=False,
        elem_id="lora-guard-cases-table",
    )
    gr.JSON(
        value=data["manifest"]["missing_artifacts"],
        label="Missing Artifacts",
        elem_id="model-lab-missing-artifacts-json",
    )


def render_model_lab_summary(data: dict[str, Any]) -> str:
    """生成 Model Lab 顶部和 LayoutLMv3 摘要。"""

    metrics = data["layout_metrics"]
    manifest = data["manifest"]
    missing = manifest["missing_artifacts"]
    return (
        "## Model Lab\n\n"
        "**Model Lab 展示真实离线实验 artifacts。不是当前网页实时模型推理。"
        "不加载 LayoutLMv3、Qwen 或真实 LoRA。**\n\n"
        "### LayoutLMv3 Extraction Lab\n\n"
        f"- OCR + Regex baseline macro F1: `{metrics['baseline_macro_f1']:.4f}`\n"
        f"- First LayoutLMv3 macro F1: `{metrics['first_layoutlmv3_macro_f1']:.4f}`\n"
        f"- Corrected LayoutLMv3 macro F1: `{metrics['corrected_layoutlmv3_macro_f1']:.4f}`\n"
        f"- Hybrid macro F1: `{metrics['hybrid_macro_f1']:.4f}`\n"
        f"- Date F1 before fix: `{metrics['date_f1_before_fix']:.4f}`\n"
        f"- Date F1 after fix: `{metrics['date_f1_after_fix']:.4f}`\n"
        f"- evaluation_split = `{metrics['evaluation_split']}`\n"
        f"- inference_scope = `{metrics['inference_scope']}`\n"
        f"- official_test=false\n\n"
        "Selected predictions are field-level JSON only. Public receipt images are not "
        "included because image source, license, and privacy review are not part of "
        "this package.\n\n"
        "### Missing Artifacts\n\n"
        + "\n".join(
            f"- `{item['artifact']}`: {item['status']} - {item['note']}"
            for item in missing
        )
    )


def render_lora_summary(data: dict[str, Any]) -> str:
    """生成 LoRA 摘要，明确离线和失败口径。"""

    metrics = data["lora_metrics"]
    run_2 = metrics["run_2"]
    hard_gates = metrics["hard_gates"]
    return (
        "### LoRA Explanation Lab\n\n"
        f"- Model: `{metrics['model']}`\n"
        f"- Backend: `{metrics['backend']}`\n"
        "- Runtime: ModelScope real offline experiment result\n"
        f"- Dataset: seed `{metrics['dataset']['seed']}`, train `{metrics['dataset']['train']}`, "
        f"validation `{metrics['dataset']['validation']}`, test `{metrics['dataset']['test']}`\n"
        f"- Second adapter hard gate passed: `{str(run_2['hard_gate_passed']).lower()}`\n"
        "- 第二轮 adapter 未通过 hard gate。\n"
        "- 第三次训练暂停。\n"
        "- LoRA 不作为默认审核解释器。\n"
        "- 真实 LoRA 当前没有在网页运行。\n"
        "- Guard cases explicitly distinguish `real_offline_model_output`, "
        "`test_fixture`, and `demo_fixture` when present.\n\n"
        "Hard gates:\n"
        + "\n".join(f"- `{key}`: `{value}`" for key, value in hard_gates.items())
    )


def layout_metric_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理 LayoutLMv3 指标表。"""

    metrics = data["layout_metrics"]
    keys = [
        "baseline_macro_f1",
        "first_layoutlmv3_macro_f1",
        "corrected_layoutlmv3_macro_f1",
        "hybrid_macro_f1",
        "date_f1_before_fix",
        "date_f1_after_fix",
        "evaluation_split",
        "inference_scope",
        "official_test",
    ]
    return [[key, _format_value(metrics[key])] for key in keys]


def layout_field_f1_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理字段级 F1 表。"""

    metrics = data["layout_metrics"]["field_metrics"]
    rows = []
    for index, field in enumerate(metrics["baseline_ocr_regex"]):
        rows.append(
            [
                field["field"],
                f"{field['f1']:.4f}",
                f"{metrics['first_layoutlmv3'][index]['f1']:.4f}",
                f"{metrics['corrected_layoutlmv3'][index]['f1']:.4f}",
            ]
        )
    return rows


def layout_training_curve_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理 LayoutLMv3 训练曲线表。"""

    curve = data["layout_curve"]
    return [
        [
            str(epoch),
            _format_value(curve["train_loss"][index]),
            _format_value(curve["validation_loss"][index]),
            _format_value(curve["token_f1"][index]),
            _format_value(curve["field_macro_f1"][index]),
        ]
        for index, epoch in enumerate(curve["epochs"])
    ]


def layout_prediction_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理 selected prediction 表。"""

    rows = []
    for case in data["layout_predictions"]["cases"]:
        rows.append(
            [
                case["case_id"],
                case["ground_truth"]["date"],
                case["prediction"]["legacy_date"],
                case["prediction"]["cleaned_date"],
                case["error_attribution"],
            ]
        )
    return rows


def lora_metric_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理两轮 LoRA 指标表。"""

    metrics = data["lora_metrics"]
    rows = []
    for run_key in ("run_1", "run_2"):
        run = metrics[run_key]
        for variant_key, variant_label in (
            ("base_metrics", "base"),
            ("fine_tuned_metrics", "fine_tuned"),
        ):
            for metric, value in run[variant_key].items():
                rows.append([run["id"], variant_label, metric, _format_value(value)])
    return rows


def lora_training_curve_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理 LoRA loss 表，缺失字段保留 null。"""

    curves = data["lora_curves"]
    rows = []
    run_1 = curves["run_1"]
    rows.append([run_1["id"], "null", "null", "null"])
    run_2 = curves["run_2"]
    for index, epoch in enumerate(run_2["epochs"]):
        rows.append(
            [
                run_2["id"],
                str(epoch),
                _format_value(run_2["train_loss"][index]),
                _format_value(run_2["validation_loss"][index]),
            ]
        )
    return rows


def lora_hallucination_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理真实报告中的幻觉案例。"""

    return [
        [
            case["run_id"],
            case["sample_id"],
            case["hallucination_type"],
            case["unsupported_content"],
            case["source_file"],
        ]
        for case in data["lora_hallucinations"]["cases"]
    ]


def lora_guard_case_rows(data: dict[str, Any]) -> list[list[str]]:
    """整理 Guard/Fallback 案例并保留来源类型。"""

    return [
        [
            case["case_id"],
            case["source_type"],
            _format_value(case["guard_passed"]),
            _format_value(case["fallback_reason"]),
            case["final_source"],
            case["evidence_scope"],
        ]
        for case in data["lora_guard_cases"]["cases"]
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
