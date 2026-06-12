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
    expected_tabs = ["Invoice Audit", "Model Lab", "Architecture"]
    for label in expected_tabs:
        if label not in tab_labels:
            errors.append(f"missing_tab:{label}")

    artifacts = load_model_lab_artifacts()
    model_lab_text = render_model_lab_summary(artifacts)
    required_model_lab_terms = [
        "offline_checkpoint_inference",
        "local_validation_split_seed_42",
        "official_test=false",
        "0.8067",
        "0.1423",
        "0.8764",
        "public_receipt_images_for_selected_predictions",
    ]
    for term in required_model_lab_terms:
        if term not in model_lab_text:
            errors.append(f"model_lab_missing:{term}")

    required_architecture_terms = [
        "Invoice",
        "OCR + LayoutLMv3",
        "Agent Tools",
        "Three-Way Match",
        "Policy RAG",
        "Risk Engine",
        "Canonical Facts",
        "Deterministic Template",
        "Optional Controlled Rewrite",
        "Guard",
        "Fallback",
        "Audit Trail",
        "AuditReport",
        "第三次训练暂停",
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
