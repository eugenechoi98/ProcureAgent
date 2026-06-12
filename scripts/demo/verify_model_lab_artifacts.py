"""校验 Model Lab 轻量 artifacts 是否满足离线展示边界。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_LAB = ROOT / "demo" / "model_lab"


REQUIRED_FILES = [
    "README.md",
    "manifest.json",
    "layoutlmv3/metrics.json",
    "layoutlmv3/training_curve.json",
    "layoutlmv3/selected_predictions.json",
    "layoutlmv3/error_analysis.json",
    "layoutlmv3/README.md",
    "lora/metrics.json",
    "lora/training_curves.json",
    "lora/hallucination_cases.json",
    "lora/guard_cases.json",
    "lora/README.md",
]


def read_json(relative_path: str) -> dict[str, Any]:
    """读取 artifacts JSON。"""
    return json.loads((MODEL_LAB / relative_path).read_text(encoding="utf-8"))


def main() -> None:
    """输出只读校验 JSON。"""
    errors: list[str] = []
    missing_files = [path for path in REQUIRED_FILES if not (MODEL_LAB / path).exists()]

    manifest = read_json("manifest.json") if not missing_files else {}
    layout_metrics = read_json("layoutlmv3/metrics.json") if not missing_files else {}
    lora_metrics = read_json("lora/metrics.json") if not missing_files else {}

    if missing_files:
        errors.append("required_files_missing")
    if manifest and manifest.get("offline_only") is not True:
        errors.append("manifest_offline_only_not_true")
    if manifest and manifest.get("live_inference") is not False:
        errors.append("manifest_live_inference_not_false")
    if manifest and manifest.get("model_weights_included") is not False:
        errors.append("manifest_model_weights_included_not_false")
    if layout_metrics and layout_metrics.get("official_test") is not False:
        errors.append("layoutlmv3_official_test_not_false")
    if layout_metrics and layout_metrics.get("inference_scope") != "offline_checkpoint_inference":
        errors.append("layoutlmv3_inference_scope_unexpected")
    if layout_metrics and layout_metrics.get("evaluation_split") != "local_validation_split_seed_42":
        errors.append("layoutlmv3_evaluation_split_unexpected")
    if lora_metrics and lora_metrics.get("run_2", {}).get("hard_gate_passed") is not False:
        errors.append("lora_run_2_hard_gate_not_false")
    if (
        lora_metrics
        and lora_metrics.get("run_2", {}).get(
            "local_checkpoint_adapter_predictions_or_runtime_copy_present"
        )
        is not False
    ):
        errors.append("lora_run_2_missing_artifact_flag_not_false")

    result = {
        "ready": not missing_files and not errors,
        "offline_only": manifest.get("offline_only"),
        "live_inference": manifest.get("live_inference"),
        "model_weights_included": manifest.get("model_weights_included"),
        "official_test": layout_metrics.get("official_test"),
        "layoutlmv3": {
            "evaluation_split": layout_metrics.get("evaluation_split"),
            "inference_scope": layout_metrics.get("inference_scope"),
            "baseline_macro_f1": layout_metrics.get("baseline_macro_f1"),
            "corrected_layoutlmv3_macro_f1": layout_metrics.get(
                "corrected_layoutlmv3_macro_f1"
            ),
        },
        "lora": {
            "run_2_hard_gate_passed": lora_metrics.get("run_2", {}).get("hard_gate_passed"),
            "run_2_local_runtime_artifacts_present": lora_metrics.get("run_2", {}).get(
                "local_checkpoint_adapter_predictions_or_runtime_copy_present"
            ),
        },
        "missing_files": missing_files,
        "missing_artifacts": manifest.get("missing_artifacts", []),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
