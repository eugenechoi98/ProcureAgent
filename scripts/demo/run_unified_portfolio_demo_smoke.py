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
from demo.invoice_case_view import load_invoice_case_catalog, preview_values
from demo.model_lab_view import load_model_lab_artifacts


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
    expected_tabs = [
        "产品总览",
        "Scenario Demo",
        "完整流程视频",
        "GitHub / 运行边界",
    ]
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
        preview = preview_values(case_catalog, case_id)
        if preview[4][0][1] != "尚未运行":
            errors.append(f"invoice_match_prepopulated:{case_id}")
        if preview[5][0][1] != "尚未运行":
            errors.append(f"invoice_evidence_prepopulated:{case_id}")
    for elem_id in (
        "main-ocr-result",
        "main-risk-card",
        "main-action-card",
        "main-final-explanation",
        "main-result-card",
        "path-a-vendor",
        "path-a-amount",
        "path-a-po",
        "path-a-grn",
        "path-a-run",
        "path-a-summary",
        "path-b-tab",
        "case-validation-summary",
        "invoice-case-image",
        "invoice-case-extraction",
        "case-explanation-mode-selector",
        "explanation-layer-trace",
    ):
        if not _component_props(components, elem_id):
            errors.append(f"invoice_case_component_missing:{elem_id}")

    case_selector = _component_props(components, "demo-case-selector")
    case_values = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in case_selector.get("choices", [])
    }
    if case_values != set(case_catalog):
        errors.append("case_validation_does_not_include_five_cases")
    mode_selector = _component_props(components, "case-explanation-mode-selector")
    if mode_selector.get("value") != "LoRA OFF":
        errors.append("explanation_default_not_template_view")
    mode_choices = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in mode_selector.get("choices", [])
    }
    if mode_choices != {"LoRA OFF", "LoRA ON"}:
        errors.append("explanation_view_choices_missing")
    artifacts = load_model_lab_artifacts()

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
        "default_mode": _component_value(components, "case-explanation-mode-selector"),
        "invoice_cases": {
            "count": len(case_catalog),
            "case_ids": list(case_catalog),
            "synthetic_images": all(
                case["source_type"] == "synthetic_imagegen"
                for case in case_catalog.values()
            ),
            "single_case_f1_claim": False,
        },
        "case_validation": {
            "count": len(case_catalog),
            "case_ids": list(case_catalog),
            "model_weights_included": False,
            "single_case_f1_claim": False,
            "live_layoutlmv3_required": False,
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
