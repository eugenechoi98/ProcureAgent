"""离线构建统一 Portfolio Demo，不启动长期服务。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.app import build_app
from demo.architecture_view import ARCHITECTURE_MARKDOWN
from demo.invoice_case_view import load_invoice_case_catalog
from demo.model_lab_view import load_model_lab_artifacts, render_model_lab_summary


def run_smoke() -> dict[str, Any]:
    """构建统一 Demo 并检查只读页面证据。"""

    errors: list[str] = []
    app = build_app()
    config = app.get_config_file()
    components = config["components"]
    tab_labels = [
        item.get("props", {}).get("label")
        for item in components
        if item.get("type") == "tabitem"
    ]
    expected_tabs = ["发票审核", "模型实验", "系统架构"]
    for label in expected_tabs:
        if label not in tab_labels:
            errors.append(f"missing_tab:{label}")
    if tab_labels != expected_tabs:
        errors.append("unexpected_tab_structure")

    case_catalog = load_invoice_case_catalog()
    if len(case_catalog) != 5:
        errors.append("invoice_case_count_not_five")
    for case_id, case in case_catalog.items():
        if case["source_type"] != "synthetic_imagegen":
            errors.append(f"invoice_case_source_not_synthetic:{case_id}")
        if "不证明" not in case["scope_note"]:
            errors.append(f"invoice_case_scope_missing:{case_id}")
    for elem_id in (
        "invoice-case-brief",
        "invoice-case-image-note",
        "invoice-case-image",
        "invoice-case-extraction",
        "invoice-case-match",
        "invoice-case-evidence",
        "invoice-case-risk-action",
        "invoice-case-explanation",
    ):
        if not _component_props(components, elem_id):
            errors.append(f"invoice_case_component_missing:{elem_id}")

    artifacts = load_model_lab_artifacts()
    model_lab_text = "\n".join(
        str(item.get("props", {}).get("value", ""))
        for item in components
        if item.get("type") == "markdown"
    )
    required_model_lab_terms = [
        "真实离线模型实验结果",
        "OCR + Regex baseline Macro F1",
        "修复后 LayoutLMv3 Macro F1",
        "日期字段 F1",
        "offline_checkpoint_inference",
        "local_validation_split_seed_42",
        "official_test=false",
        "0.8067",
        "0.1423",
        "0.8764",
        "确定性模板 + 可选受控改写 + 输出守卫 + 模板回退",
    ]
    for term in required_model_lab_terms:
        if term not in model_lab_text:
            errors.append(f"model_lab_missing:{term}")

    raw_evidence = _component_props(components, "model-lab-raw-evidence")
    if raw_evidence.get("open") is not False:
        errors.append("model_lab_raw_evidence_not_collapsed")
    if any(
        item.get("props", {}).get("label") == "缺失 artifacts"
        for item in components
    ):
        errors.append("model_lab_missing_artifacts_visible")
    guard_visual_text = "\n".join(
        str(_component_value(components, elem_id) or "")
        for elem_id in (
            "lora-guard-visual-intro",
            "lora-guard-visual-raw-output",
            "lora-guard-visual-result",
            "lora-guard-visual-fallback",
        )
    )
    for term in (
        "LoRA 幻觉与 Guard 拦截示例",
        "GRN-20260149",
        "REJECT",
        "未补全未知 GRN",
        "Phase 3I",
    ):
        if term not in guard_visual_text:
            errors.append(f"model_lab_guard_visual_missing:{term}")

    required_architecture_terms = [
        "受控采购审核 Agent",
        "autonomous LLM",
        "发票图片",
        "OCR + LayoutLMv3 字段抽取",
        "Agent 工具",
        "三单匹配",
        "Policy RAG",
        "风险规则引擎",
        "规范化审核事实",
        "确定性模板",
        "受控 rewrite",
        "Guard",
        "fallback",
        "审计轨迹",
        "审核报告",
    ]
    for term in required_architecture_terms:
        if term not in ARCHITECTURE_MARKDOWN:
            errors.append(f"architecture_missing:{term}")

    return {
        "ready": not errors,
        "scope": "unified_portfolio_demo_offline_build",
        "tabs": tab_labels,
        "default_case": _component_value(components, "demo-case-selector"),
        "default_mode": _component_value(components, "explanation-mode-selector"),
        "invoice_cases": {
            "count": len(case_catalog),
            "case_ids": list(case_catalog),
            "synthetic_images": all(
                case["source_type"] == "synthetic_imagegen"
                for case in case_catalog.values()
            ),
            "single_case_f1_claim": False,
        },
        "model_lab": {
            "manifest_loaded": bool(artifacts["manifest"]),
            "layoutlmv3_metrics_loaded": bool(artifacts["layout_metrics"]),
            "lora_metrics_loaded": bool(artifacts["lora_metrics"]),
            "official_test": artifacts["layout_metrics"]["official_test"],
            "inference_scope": artifacts["layout_metrics"]["inference_scope"],
            "evaluation_split": artifacts["layout_metrics"]["evaluation_split"],
            "second_lora_hard_gate_passed": artifacts["lora_metrics"]["run_2"][
                "hard_gate_passed"
            ],
            "missing_artifacts": artifacts["manifest"]["missing_artifacts"],
        },
        "architecture": {
            "contains_required_chain": not any(
                error.startswith("architecture_missing:") for error in errors
            )
        },
        "requirements": {
            "api_key_required": False,
            "network_required": False,
            "gpu_required": False,
            "layoutlmv3_required": False,
            "qwen_required": False,
            "real_lora_required": False,
            "long_running_service_started": False,
            "browser_opened": False,
        },
        "errors": errors,
    }


def _component_value(components: list[dict[str, Any]], elem_id: str) -> Any:
    for component in components:
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props.get("value")
    return None


def _component_props(components: list[dict[str, Any]], elem_id: str) -> dict[str, Any]:
    for component in components:
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props
    return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run offline unified portfolio demo smoke checks."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. No file is written by default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    result = run_smoke()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
