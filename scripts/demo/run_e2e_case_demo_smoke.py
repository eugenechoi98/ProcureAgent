"""离线检查 H1 端到端证据链展示，不启动长期服务。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from demo.e2e_case_view import load_e2e_case_catalog, e2e_case_values


def run_smoke() -> dict[str, Any]:
    """检查三个案例的来源、展示值和关键 claim 边界。"""

    errors: list[str] = []
    catalog = load_e2e_case_catalog()
    expected_ids = [
        "case_a_standard_pass",
        "case_b_date_layout_challenge",
        "case_c_lora_guard_fallback",
    ]
    if list(catalog) != expected_ids:
        errors.append("unexpected_case_catalog")

    for case_id in expected_ids:
        values = e2e_case_values(catalog[case_id])
        if len(values) != 13:
            errors.append(f"unexpected_component_value_count:{case_id}")

    for case_id in expected_ids[:2]:
        case = catalog[case_id]
        manifest = case["manifest"]
        if manifest["layoutlmv3_prediction_type"] != "real_checkpoint_inference":
            errors.append(f"layout_evidence_not_real:{case_id}")
        if manifest["phase2_context_type"] != "mock_po_grn_context":
            errors.append(f"mock_context_not_explicit:{case_id}")
        if not manifest["image_is_public_safe"]:
            errors.append(f"image_not_public_safe:{case_id}")
        gallery = e2e_case_values(case)[2]
        if len(gallery) != 3 or not all(Path(item[0]).is_file() for item in gallery):
            errors.append(f"image_evidence_missing:{case_id}")

    case_b_text = "\n".join(
        str(item) for item in e2e_case_values(catalog[expected_ids[1]])
    )
    if "单样本证据" not in case_b_text or "整体 Date F1" not in case_b_text:
        errors.append("date_case_claim_boundary_missing")

    case_c = catalog[expected_ids[2]]
    case_c_values = e2e_case_values(case_c)
    if case_c_values[2] != []:
        errors.append("guard_case_should_not_have_image")
    if case_c["manifest"]["lora_result_type"] != "real_offline_model_output":
        errors.append("lora_output_not_real_offline_artifact")
    if case_c["guard_result"]["decision"] != "REJECT":
        errors.append("guard_did_not_reject")
    if (
        case_c["guard_result"]["expected_key_violation"]
        != "unknown_identifier:GRN-20260149"
    ):
        errors.append("guard_violation_mismatch")

    return {
        "ready": not errors,
        "scope": "e2e_case_demo_offline_smoke",
        "case_ids": list(catalog),
        "case_count": len(catalog),
        "sroie_images_included": True,
        "manual_privacy_review": "passed_no_masking_required",
        "license_attribution": "CC BY 4.0 attribution retained",
        "layoutlmv3_live_inference": False,
        "real_lora_live_inference": False,
        "model_weights_included": False,
        "single_case_f1_claim": False,
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
