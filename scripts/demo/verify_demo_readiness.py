"""只读验证 Phase 3H 固定 Demo Cases 的本地离线准备状态。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "phase3h_demo_cases.json"
EXPECTED_CASE_COUNT = 13
REQUIRED_CASE_IDS = {
    "normal_invoice",
    "shadow_mode_trace_only",
    "experimental_guard_pass",
    "experimental_guard_fail",
    "provider_runtime_error_fallback",
    "invalid_output_fallback",
    "high_risk_template_fallback",
}
REQUIRED_TOP_LEVEL_FIELDS = {
    "case_id",
    "facts",
    "mode",
    "provider_behavior",
    "expected_source",
    "expected_fallback",
}
REQUIRED_FACT_FIELDS = {
    "risk_level",
    "recommended_action",
    "anomaly_types",
}
ALLOWED_RISKS = {"low", "medium", "high"}
ALLOWED_ACTIONS = {"auto_approve", "request_human_approval", "reject"}
ALLOWED_SOURCES = {"template", "controlled_rewrite"}


def verify_demo_readiness(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    """返回只读 readiness 摘要，不修改 fixture、模型或 artifacts。"""

    errors: list[str] = []
    cases = _load_cases(fixture_path, errors)
    case_ids: list[str] = []

    if cases is not None:
        if len(cases) != EXPECTED_CASE_COUNT:
            errors.append(
                f"expected_case_count:{EXPECTED_CASE_COUNT}:actual:{len(cases)}"
            )
        for index, case in enumerate(cases):
            case_ids.append(_validate_case(case, index, errors))
        duplicates = sorted(
            case_id
            for case_id in set(case_ids)
            if case_id and case_ids.count(case_id) > 1
        )
        for case_id in duplicates:
            errors.append(f"duplicate_case_id:{case_id}")
        missing_cases = sorted(REQUIRED_CASE_IDS - set(case_ids))
        for case_id in missing_cases:
            errors.append(f"missing_required_case:{case_id}")

    return {
        "ready": not errors,
        "readiness_scope": "local_offline_demo_only",
        "fixture_path": str(fixture_path.resolve()),
        "fixture_exists": fixture_path.is_file(),
        "case_count": len(cases) if cases is not None else 0,
        "expected_case_count": EXPECTED_CASE_COUNT,
        "unique_case_ids": len(case_ids) == len(set(case_ids)),
        "required_cases": {
            case_id: case_id in set(case_ids) for case_id in sorted(REQUIRED_CASE_IDS)
        },
        "requirements": {
            "api_key_required": False,
            "network_required": False,
            "gpu_required": False,
            "qwen_required": False,
            "lora_required": False,
            "service_start_required": False,
        },
        "checks": {
            "fixed_risk": not any("risk_level" in error for error in errors),
            "fixed_action": not any(
                "recommended_action" in error for error in errors
            ),
            "anomaly_types_present": not any(
                "anomaly_types" in error for error in errors
            ),
            "explanation_source_present": not any(
                "expected_source" in error for error in errors
            ),
            "fallback_expectation_present": not any(
                "expected_fallback" in error for error in errors
            ),
        },
        "errors": errors,
    }


def _load_cases(
    fixture_path: Path, errors: list[str]
) -> list[dict[str, Any]] | None:
    """读取 fixture，任何结构错误都进入 JSON 摘要。"""

    if not fixture_path.is_file():
        errors.append("fixture_missing")
        return None
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"fixture_parse_error:{exc.__class__.__name__}")
        return None
    if not isinstance(payload, list):
        errors.append("fixture_must_be_array")
        return None
    return payload


def _validate_case(case: Any, index: int, errors: list[str]) -> str:
    """校验单个 case 的固定输入和固定预期。"""

    prefix = f"case[{index}]"
    if not isinstance(case, dict):
        errors.append(f"{prefix}:must_be_object")
        return ""

    missing_top = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(case))
    for field in missing_top:
        errors.append(f"{prefix}:missing_field:{field}")

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        errors.append(f"{prefix}:invalid_case_id")
        case_id = ""

    facts = case.get("facts")
    if not isinstance(facts, dict):
        errors.append(f"{prefix}:facts:must_be_object")
        return case_id
    for field in sorted(REQUIRED_FACT_FIELDS - set(facts)):
        errors.append(f"{prefix}:facts:missing_field:{field}")

    risk = facts.get("risk_level")
    if risk not in ALLOWED_RISKS:
        errors.append(f"{prefix}:facts:invalid_risk_level")
    action = facts.get("recommended_action")
    if action not in ALLOWED_ACTIONS:
        errors.append(f"{prefix}:facts:invalid_recommended_action")
    if not isinstance(facts.get("anomaly_types"), list):
        errors.append(f"{prefix}:facts:invalid_anomaly_types")
    if case.get("expected_source") not in ALLOWED_SOURCES:
        errors.append(f"{prefix}:invalid_expected_source")
    if "expected_fallback" not in case:
        errors.append(f"{prefix}:missing_field:expected_fallback")
    elif case["expected_fallback"] is not None and not isinstance(
        case["expected_fallback"], str
    ):
        errors.append(f"{prefix}:invalid_expected_fallback")
    return case_id


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数。"""

    parser = argparse.ArgumentParser(
        description="Verify local offline Phase 3H demo readiness."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Demo fixture JSON path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. No file is written by default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """打印结构化 JSON，显式指定 output 时才写文件。"""

    args = build_parser().parse_args(argv)
    result = verify_demo_readiness(args.fixture)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
