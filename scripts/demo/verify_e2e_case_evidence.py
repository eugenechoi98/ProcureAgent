"""验证端到端证据包的文件、来源类型和 claim 边界。"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = PROJECT_ROOT / "demo" / "e2e_cases"
REPORT_PATH = PROJECT_ROOT / "reports" / "demo" / "e2e_case_evidence_report.json"
EXPECTED_CASES = {
    "case_a_standard_pass",
    "case_b_date_layout_challenge",
    "case_c_lora_guard_fallback",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def verify() -> dict[str, Any]:
    """返回可供 CI 和人工验收使用的稳定 JSON。"""

    errors: list[str] = []
    case_results: list[dict[str, Any]] = []
    if not REPORT_PATH.is_file():
        return {
            "ready": False,
            "scope": "batch_h0_e2e_case_evidence",
            "errors": ["missing_report"],
        }
    report = _load(REPORT_PATH)
    case_dirs = {path.name for path in EVIDENCE_ROOT.iterdir() if path.is_dir()}
    if case_dirs != EXPECTED_CASES:
        errors.append("unexpected_case_set")

    for case_id in sorted(EXPECTED_CASES):
        case_dir = EVIDENCE_ROOT / case_id
        manifest_path = case_dir / "manifest.json"
        if not manifest_path.is_file():
            errors.append(f"missing_manifest:{case_id}")
            continue
        manifest = _load(manifest_path)
        required_manifest_keys = {
            "case_id",
            "case_title",
            "source_type",
            "source_license_or_note",
            "image_is_public_safe",
            "layoutlmv3_prediction_type",
            "phase2_result_type",
            "lora_result_type",
            "guard_result_type",
            "claims_allowed",
            "claims_forbidden",
        }
        missing_keys = sorted(required_manifest_keys - set(manifest))
        if missing_keys:
            errors.append(f"manifest_keys:{case_id}:{','.join(missing_keys)}")
        if not manifest.get("claims_allowed") or not manifest.get("claims_forbidden"):
            errors.append(f"claim_boundaries_missing:{case_id}")
        hashes = manifest.get("evidence_file_sha256", {})
        if not hashes:
            errors.append(f"evidence_hashes_missing:{case_id}")
        for name, expected_hash in hashes.items():
            path = case_dir / name
            if not path.is_file() or _sha256(path) != expected_hash:
                errors.append(f"evidence_hash_mismatch:{case_id}:{name}")

        if case_id.startswith("case_a") or case_id.startswith("case_b"):
            required_files = {
                "source_invoice.png",
                "ocr_boxes.png",
                "layoutlmv3_predictions.png",
                "ocr_output.json",
                "extracted_fields.json",
                "phase2_audit_input.json",
                "phase2_audit_result.json",
                "final_audit_report.json",
                "notes.md",
            }
            if case_id.startswith("case_b"):
                required_files.add("date_reconstruction.json")
            if manifest.get("source_type") != "SROIE":
                errors.append(f"wrong_source_type:{case_id}")
            if manifest.get("layoutlmv3_prediction_type") != "real_checkpoint_inference":
                errors.append(f"not_real_checkpoint:{case_id}")
            if manifest.get("phase2_result_type") != "real_runtime_engine":
                errors.append(f"not_runtime_phase2:{case_id}")
            audit_input = _load(case_dir / "phase2_audit_input.json")
            provenance = audit_input.get("field_provenance", {})
            for key in ("invoice_number", "po_number"):
                if "mock" not in provenance.get(key, ""):
                    errors.append(f"mock_provenance_missing:{case_id}:{key}")
            audit_result = _load(case_dir / "phase2_audit_result.json")
            if audit_result.get("risk_level") != "low":
                errors.append(f"unexpected_risk:{case_id}")
            extracted = _load(case_dir / "extracted_fields.json")
            source_size = Image.open(case_dir / "source_invoice.png").size
            for row in extracted.get("word_predictions", []):
                box = row.get("bbox", [])
                if len(box) != 4 or any(value < 0 or value > 1000 for value in box):
                    errors.append(f"invalid_normalized_bbox:{case_id}")
                    break
            if not any(
                row.get("predicted_label") != "O"
                for row in extracted.get("word_predictions", [])
            ):
                errors.append(f"no_predicted_fields:{case_id}")
            for image_name in ("ocr_boxes.png", "layoutlmv3_predictions.png"):
                if Image.open(case_dir / image_name).size != source_size:
                    errors.append(f"visual_size_mismatch:{case_id}:{image_name}")
        else:
            required_files = {
                "audit_facts.json",
                "lora_raw_output.txt",
                "guard_result.json",
                "fallback_explanation.md",
                "final_explanation.md",
                "final_audit_report.json",
                "notes.md",
            }
            if manifest.get("lora_result_type") != "real_offline_model_output":
                errors.append("lora_evidence_not_real_offline")
            if manifest.get("guard_result_type") != "real_guard_check":
                errors.append("guard_evidence_not_real_check")
            guard = _load(case_dir / "guard_result.json")
            if guard.get("passed") is not False or guard.get("decision") != "REJECT":
                errors.append("guard_not_rejected")
            if "unknown_identifier:GRN-20260149" not in guard.get("violations", []):
                errors.append("expected_grn_violation_missing")

        missing_files = sorted(
            name for name in required_files if not (case_dir / name).is_file()
        )
        if missing_files:
            errors.append(f"missing_files:{case_id}:{','.join(missing_files)}")
        case_results.append(
            {
                "case_id": case_id,
                "source_type": manifest.get("source_type"),
                "layoutlmv3_prediction_type": manifest.get(
                    "layoutlmv3_prediction_type"
                ),
                "phase2_result_type": manifest.get("phase2_result_type"),
                "lora_result_type": manifest.get("lora_result_type"),
                "guard_result_type": manifest.get("guard_result_type"),
            }
        )

    if report.get("generated_case_count") != 3:
        errors.append("report_case_count")
    if report.get("local_assets", {}).get("checkpoint_included") is not False:
        errors.append("checkpoint_must_not_be_included")
    if report.get("local_assets", {}).get("lora_weights_included") is not False:
        errors.append("lora_weights_must_not_be_included")
    return {
        "ready": not errors,
        "scope": "batch_h0_e2e_case_evidence",
        "case_count": len(case_results),
        "cases": case_results,
        "real_public_images_found": report.get("real_public_images_found"),
        "image_prediction_one_to_one": report.get("image_prediction_one_to_one"),
        "bbox_visualization_generated": report.get(
            "bbox_visualization_generated"
        ),
        "phase2_runtime_audit_generated": report.get(
            "phase2_runtime_audit_generated"
        ),
        "real_lora_guard_case_generated": report.get(
            "real_lora_guard_case_generated"
        ),
        "model_weights_included": False,
        "errors": errors,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
