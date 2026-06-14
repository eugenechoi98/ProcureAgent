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
        headers=["指标", "数值"],
        datatype=["str", "str"],
        label="LayoutLMv3 实验指标",
        interactive=False,
        elem_id="layoutlmv3-metrics-table",
    )
    gr.Dataframe(
        value=layout_field_f1_rows(data),
        row_count=len(layout_field_f1_rows(data)),
        headers=[
            "字段",
            "OCR + Regex 基线",
            "首次 LayoutLMv3",
            "修正后 LayoutLMv3",
        ],
        datatype=["str", "str", "str", "str"],
        label="LayoutLMv3 字段级 F1",
        interactive=False,
        elem_id="layoutlmv3-field-f1-table",
    )
    gr.Dataframe(
        value=layout_training_curve_rows(data),
        row_count=len(layout_training_curve_rows(data)),
        headers=["轮次", "训练损失", "验证损失", "Token F1", "字段 Macro F1"],
        datatype=["str", "str", "str", "str", "str"],
        label="LayoutLMv3 训练曲线",
        interactive=False,
        elem_id="layoutlmv3-training-curve-table",
    )
    gr.Dataframe(
        value=layout_prediction_rows(data),
        row_count=len(layout_prediction_rows(data)),
        headers=[
            "案例编号",
            "真实日期",
            "修复前日期",
            "清洗后日期",
            "错误归因",
        ],
        datatype=["str", "str", "str", "str", "str"],
        label="真实离线预测样例",
        interactive=False,
        elem_id="layoutlmv3-predictions-table",
    )
    gr.JSON(
        value=data["layout_errors"],
        label="LayoutLMv3 错误分析",
        elem_id="layoutlmv3-error-analysis-json",
    )
    gr.Markdown(render_lora_summary(data), elem_id="lora-summary")
    gr.Dataframe(
        value=lora_metric_rows(data),
        row_count=len(lora_metric_rows(data)),
        headers=["训练轮次", "模型版本", "指标", "数值"],
        datatype=["str", "str", "str", "str"],
        label="LoRA 实验指标",
        interactive=False,
        elem_id="lora-metrics-table",
    )
    gr.Dataframe(
        value=lora_training_curve_rows(data),
        row_count=len(lora_training_curve_rows(data)),
        headers=["训练轮次", "Epoch", "训练损失", "验证损失"],
        datatype=["str", "str", "str", "str"],
        label="LoRA 训练曲线",
        interactive=False,
        elem_id="lora-training-curves-table",
    )
    gr.Dataframe(
        value=lora_hallucination_rows(data),
        row_count=len(lora_hallucination_rows(data)),
        headers=[
            "训练编号",
            "样例编号",
            "幻觉类型",
            "无依据内容",
            "来源文件",
        ],
        datatype=["str", "str", "str", "str", "str"],
        label="LoRA 幻觉案例",
        interactive=False,
        elem_id="lora-hallucination-cases-table",
    )
    gr.Dataframe(
        value=lora_guard_case_rows(data),
        row_count=len(lora_guard_case_rows(data)),
        headers=[
            "案例编号",
            "来源类型",
            "守卫是否通过",
            "回退原因",
            "最终来源",
            "证据范围",
        ],
        datatype=["str", "str", "str", "str", "str", "str"],
        label="守卫与回退案例",
        interactive=False,
        elem_id="lora-guard-cases-table",
    )
    gr.JSON(
        value=localized_missing_artifacts(data),
        label="缺失 artifacts",
        elem_id="model-lab-missing-artifacts-json",
    )


def render_model_lab_summary(data: dict[str, Any]) -> str:
    """生成 Model Lab 顶部和 LayoutLMv3 摘要。"""

    metrics = data["layout_metrics"]
    manifest = data["manifest"]
    missing = manifest["missing_artifacts"]
    return (
        "## 模型实验\n\n"
        "**本页展示真实离线实验 artifacts，不是当前网页实时模型推理。"
        "当前网页不会加载 LayoutLMv3、Qwen 或真实 LoRA。**\n\n"
        "### LayoutLMv3 字段抽取实验\n\n"
        f"- OCR + Regex 基线 Macro F1：`{metrics['baseline_macro_f1']:.4f}`\n"
        f"- 首次 LayoutLMv3 Macro F1：`{metrics['first_layoutlmv3_macro_f1']:.4f}`\n"
        f"- 修正后 LayoutLMv3 Macro F1：`{metrics['corrected_layoutlmv3_macro_f1']:.4f}`\n"
        f"- 混合方案 Macro F1：`{metrics['hybrid_macro_f1']:.4f}`\n"
        f"- 日期 F1 修复前：`{metrics['date_f1_before_fix']:.4f}`\n"
        f"- 日期 F1 修复后：`{metrics['date_f1_after_fix']:.4f}`\n"
        f"- evaluation_split = `{metrics['evaluation_split']}`：本地固定验证集\n"
        f"- inference_scope = `{metrics['inference_scope']}`：离线 checkpoint 推理\n"
        "- official_test=false：不是官方测试集结果\n\n"
        "真实离线预测样例只保留字段级 JSON。由于图片来源、许可证与隐私尚未完成公开审查，"
        "本发布包不包含公开票据图片。\n\n"
        "### 缺失 artifacts\n\n"
        + "\n".join(_localized_missing_artifact_line(item) for item in missing)
    )


def render_lora_summary(data: dict[str, Any]) -> str:
    """生成 LoRA 摘要，明确离线和失败口径。"""

    metrics = data["lora_metrics"]
    run_2 = metrics["run_2"]
    hard_gates = metrics["hard_gates"]
    return (
        "### LoRA 异常解释实验\n\n"
        f"- 模型：`{metrics['model']}`\n"
        f"- 训练后端：`{metrics['backend']}`\n"
        "- 运行来源：ModelScope 真实离线实验结果\n"
        f"- 数据集：seed `{metrics['dataset']['seed']}`，训练 `{metrics['dataset']['train']}`，"
        f"验证 `{metrics['dataset']['validation']}`，测试 `{metrics['dataset']['test']}`\n"
        f"- 第二轮 Adapter 是否通过 hard gate：`{str(run_2['hard_gate_passed']).lower()}`\n"
        "- 第二轮 adapter 未通过 hard gate。\n"
        "- 第三次训练暂停。\n"
        "- LoRA 不作为默认审核解释器。\n"
        "- 真实 LoRA 当前没有在网页运行。\n"
        "- 守卫案例会明确区分 `real_offline_model_output`、`test_fixture` 和 `demo_fixture`。\n\n"
        "hard gate 阈值：\n"
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


def localized_missing_artifacts(data: dict[str, Any]) -> list[dict[str, str]]:
    """把缺失 artifacts 的展示备注转换为中文。"""

    return [
        {
            "artifact": item["artifact"],
            "status": _localized_artifact_status(item["status"]),
            "note": _localized_artifact_note(item["artifact"]),
        }
        for item in data["manifest"]["missing_artifacts"]
    ]


def _localized_missing_artifact_line(item: dict[str, str]) -> str:
    return (
        f"- `{item['artifact']}`：{_localized_artifact_status(item['status'])} - "
        f"{_localized_artifact_note(item['artifact'])}"
    )


def _localized_artifact_status(status: str) -> str:
    return {
        "not_present_in_git": "Git 中不存在",
        "not_included": "未包含",
    }.get(status, status)


def _localized_artifact_note(artifact: str) -> str:
    return {
        "first_lora_training_curve": "首轮 LoRA 报告包含评测指标和幻觉案例，但没有提交训练/验证损失历史。",
        "second_lora_local_checkpoint_adapter_predictions_runtime_copy": "第二轮只保留经确认的 ModelScope 指标，未将 checkpoint、Adapter、预测或运行时产物复制到 Git。",
        "public_receipt_images_for_selected_predictions": "预测样例只保留字段级 JSON，公开模型实验包没有复制票据图片。",
    }.get(artifact, "该 artifact 当前未纳入公开展示包。")


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
