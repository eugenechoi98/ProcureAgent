"""校验 Model Lab 轻量 artifacts 的只读展示口径。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_LAB = ROOT / "demo" / "model_lab"


def load_json(relative_path: str) -> dict:
    """读取 Model Lab JSON 文件。"""
    return json.loads((MODEL_LAB / relative_path).read_text(encoding="utf-8"))


def test_manifest_keeps_offline_artifact_boundary() -> None:
    manifest = load_json("manifest.json")

    assert manifest["generated_from_existing_evidence_only"] is True
    assert manifest["offline_only"] is True
    assert manifest["live_inference"] is False
    assert manifest["model_weights_included"] is False
    assert manifest["claims_scope"]["layoutlmv3"]["official_test"] is False
    assert manifest["claims_scope"]["layoutlmv3"]["inference_scope"] == "offline_checkpoint_inference"
    assert manifest["claims_scope"]["lora"]["second_adapter_passed_hard_gates"] is False


def test_layoutlmv3_metrics_match_frozen_claims() -> None:
    metrics = load_json("layoutlmv3/metrics.json")

    assert metrics["official_test"] is False
    assert metrics["evaluation_split"] == "local_validation_split_seed_42"
    assert metrics["inference_scope"] == "offline_checkpoint_inference"
    assert round(metrics["baseline_macro_f1"], 4) == 0.4387
    assert round(metrics["corrected_layoutlmv3_macro_f1"], 4) == 0.8067
    assert round(metrics["date_f1_before_fix"], 4) == 0.1423
    assert round(metrics["date_f1_after_fix"], 4) == 0.8764


def test_layoutlmv3_predictions_are_json_only_and_real_scoped() -> None:
    predictions = load_json("layoutlmv3/selected_predictions.json")
    cases = predictions["cases"]

    assert 3 <= len(cases) <= 5
    assert all(case["source"] == "offline_checkpoint_inference" for case in cases)
    assert all(case["display_safe"] is True for case in cases)
    assert all(case["image_available"] is False for case in cases)


def test_lora_records_missing_runtime_artifacts_without_filling_gaps() -> None:
    metrics = load_json("lora/metrics.json")
    curves = load_json("lora/training_curves.json")

    assert metrics["run_2"]["hard_gate_passed"] is False
    assert metrics["run_2"]["local_checkpoint_adapter_predictions_or_runtime_copy_present"] is False
    assert curves["run_1"]["train_loss"] is None
    assert curves["run_1"]["validation_loss"] is None
    assert curves["run_1"]["missing_reason"]


def test_lora_hallucination_examples_keep_required_real_cases() -> None:
    hallucinations = load_json("lora/hallucination_cases.json")
    unsupported = {case["hallucination_type"] + ":" + case["unsupported_content"] for case in hallucinations["cases"]}

    assert "unknown_amount:8100.24" in unsupported
    assert "unknown_identifier:GRN-20260149" in unsupported
    assert "unknown_identifier:PO-77450099" in unsupported
    assert "unsupported_policy_or_approver:审批人" in unsupported
