"""离线遍历本地 Gradio Demo service，不启动长期服务。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.demo_service import DemoOutput, DemoService


def run_smoke(service: DemoService | None = None) -> dict[str, Any]:
    """验证 13 个 case 和关键 explanation mode。"""

    demo_service = service or DemoService()
    errors: list[str] = []
    cases: list[dict[str, Any]] = []
    for case_id in demo_service.case_ids:
        result = demo_service.run_case(case_id, "template")
        cases.append(_case_summary(result))
        _check_complete(result, errors)
        if result.explanation_source != "template":
            errors.append(f"{case_id}:default_source_not_template")
        if result.used_rewrite:
            errors.append(f"{case_id}:default_used_rewrite")

    mode_expectations = {
        "shadow": ("template", "shadow_mode_template_default", False),
        "experimental_guard_pass": ("controlled_rewrite", None, True),
        "experimental_guard_fail": ("template", "guard_failed", False),
        "provider_runtime_error": ("template", "model_runtime_error", False),
        "invalid_output": ("template", "invalid_lora_output", False),
    }
    modes: dict[str, dict[str, Any]] = {}
    for mode, (source, fallback, used_rewrite) in mode_expectations.items():
        result = demo_service.run_case("normal_invoice", mode)
        modes[mode] = _case_summary(result)
        if result.explanation_source != source:
            errors.append(f"{mode}:unexpected_source")
        if result.fallback_reason != fallback:
            errors.append(f"{mode}:unexpected_fallback")
        if result.used_rewrite is not used_rewrite:
            errors.append(f"{mode}:unexpected_used_rewrite")

    high_risk = demo_service.run_case(
        "high_risk_template_fallback", "experimental_guard_pass"
    )
    modes["high_risk_template_fallback"] = _case_summary(high_risk)
    if high_risk.explanation_source != "template":
        errors.append("high_risk:unexpected_source")
    if high_risk.fallback_reason != "high_risk_template_only":
        errors.append("high_risk:unexpected_fallback")

    return {
        "ready": not errors,
        "scope": "local_offline_gradio_service",
        "case_count": len(cases),
        "cases": cases,
        "mode_checks": modes,
        "requirements": {
            "api_key_required": False,
            "network_required": False,
            "gpu_required": False,
            "qwen_required": False,
            "lora_required": False,
            "long_running_service_started": False,
        },
        "errors": errors,
    }


def _check_complete(result: DemoOutput, errors: list[str]) -> None:
    """检查页面输出所需字段完整。"""

    required_text = {
        "case_id": result.case_id,
        "invoice_id": result.invoice_id,
        "risk_level": result.risk_level,
        "recommended_action": result.recommended_action,
        "explanation_text": result.explanation_text,
        "explanation_source": result.explanation_source,
        "facts_hash": result.facts_hash,
        "template_version": result.template_version,
        "prompt_version": result.prompt_version,
    }
    for field, value in required_text.items():
        if not value:
            errors.append(f"{result.case_id}:missing:{field}")
    if not isinstance(result.audit_report, dict):
        errors.append(f"{result.case_id}:invalid:audit_report")


def _case_summary(result: DemoOutput) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "execution_path": result.execution_path,
        "risk_level": result.risk_level,
        "recommended_action": result.recommended_action,
        "anomaly_types": result.anomaly_types,
        "explanation_source": result.explanation_source,
        "used_rewrite": result.used_rewrite,
        "guard_passed": result.guard_passed,
        "fallback_reason": result.fallback_reason,
        "static_fallback": result.static_fallback,
        "static_fallback_reason": result.static_fallback_reason,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local offline Gradio demo service smoke checks."
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
