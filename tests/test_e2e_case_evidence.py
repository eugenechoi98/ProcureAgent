"""Batch H0 端到端证据包边界测试。"""

from scripts.demo.verify_e2e_case_evidence import verify


def test_e2e_case_evidence_is_traceable_and_ready() -> None:
    result = verify()

    assert result["ready"] is True
    assert result["case_count"] == 3
    assert result["real_public_images_found"] is True
    assert result["image_prediction_one_to_one"] is True
    assert result["bbox_visualization_generated"] is True
    assert result["phase2_runtime_audit_generated"] is True
    assert result["real_lora_guard_case_generated"] is True
    assert result["model_weights_included"] is False
    assert result["errors"] == []


def test_e2e_case_evidence_keeps_source_types_separate() -> None:
    result = verify()
    cases = {case["case_id"]: case for case in result["cases"]}

    for case_id in ("case_a_standard_pass", "case_b_date_layout_challenge"):
        assert cases[case_id]["source_type"] == "SROIE"
        assert (
            cases[case_id]["layoutlmv3_prediction_type"]
            == "real_checkpoint_inference"
        )
        assert cases[case_id]["phase2_result_type"] == "real_runtime_engine"
        assert cases[case_id]["lora_result_type"] == "not_available"

    guard_case = cases["case_c_lora_guard_fallback"]
    assert guard_case["source_type"] == "existing_fixture"
    assert guard_case["layoutlmv3_prediction_type"] == "not_available"
    assert guard_case["phase2_result_type"] == "fixture_only"
    assert guard_case["lora_result_type"] == "real_offline_model_output"
    assert guard_case["guard_result_type"] == "real_guard_check"
