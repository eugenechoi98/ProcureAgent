"""离线验证发票案例演示目录和审核结果。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.demo_service import DemoService
from demo.invoice_case_view import load_invoice_case_catalog


def run_smoke() -> dict[str, Any]:
    """验证 5 个案例的图片、证据边界和既有审核输出。"""

    errors: list[str] = []
    catalog = load_invoice_case_catalog()
    service = DemoService()
    results: list[dict[str, Any]] = []

    if len(catalog) != 5:
        errors.append("case_count_not_five")

    for case_id, case in catalog.items():
        image_path = PROJECT_ROOT / "demo" / case["image"]
        if not image_path.is_file():
            errors.append(f"missing_image:{case_id}")
        if case["source_type"] != "synthetic_imagegen":
            errors.append(f"unsafe_source_type:{case_id}")
        if "不证明" not in case["scope_note"]:
            errors.append(f"missing_metric_scope:{case_id}")
        if any(
            row[2] != "未运行" or row[3] != "未运行"
            for row in case["extraction_rows"]
            if row[2] != "不适用"
        ):
            errors.append(f"single_image_inference_claim:{case_id}")

        result = service.run_case(case_id, case["recommended_mode"])
        if result.risk_level != case["risk_level"]:
            errors.append(f"risk_level_mismatch:{case_id}")
        if result.recommended_action != case["recommended_action"]:
            errors.append(f"recommended_action_mismatch:{case_id}")
        results.append(
            {
                "case_id": case_id,
                "risk_level": result.risk_level,
                "recommended_action": result.recommended_action,
                "explanation_source": result.explanation_source,
                "guard_passed": result.guard_passed,
                "fallback_reason": result.fallback_reason,
            }
        )

    return {
        "ready": not errors,
        "scope": "invoice_case_demo_offline_smoke",
        "case_count": len(catalog),
        "synthetic_images_only": True,
        "single_case_f1_claim": False,
        "layoutlmv3_live_inference": False,
        "real_lora_live_inference": False,
        "results": results,
        "errors": errors,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
