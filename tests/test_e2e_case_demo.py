"""H1 端到端证据链页面测试。"""

from demo.app import build_app
from demo.e2e_case_view import load_e2e_case_catalog, e2e_case_values
from scripts.demo.run_e2e_case_demo_smoke import run_smoke


def _component_props(elem_id: str) -> dict:
    for component in build_app().get_config_file()["components"]:
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props
    raise AssertionError(f"Missing component elem_id={elem_id}")


def test_e2e_catalog_keeps_evidence_sources_separate() -> None:
    catalog = load_e2e_case_catalog()

    assert list(catalog) == [
        "case_a_standard_pass",
        "case_b_date_layout_challenge",
        "case_c_lora_guard_fallback",
    ]
    for case_id in list(catalog)[:2]:
        manifest = catalog[case_id]["manifest"]
        assert manifest["source_type"] == "SROIE"
        assert manifest["layoutlmv3_prediction_type"] == "real_checkpoint_inference"
        assert manifest["phase2_result_type"] == "real_runtime_engine"
        assert manifest["phase2_context_type"] == "mock_po_grn_context"
    assert catalog["case_c_lora_guard_fallback"]["manifest"]["source_type"] == (
        "existing_fixture"
    )


def test_case_b_marks_single_sample_claim_boundary() -> None:
    values = e2e_case_values(
        load_e2e_case_catalog()["case_b_date_layout_challenge"]
    )
    rendered = "\n".join(str(item) for item in values)

    assert "单样本证据" in rendered
    assert "整体 Date F1 请见“模型实验”页" in rendered
    assert "official_test=false" in rendered


def test_case_c_has_no_image_and_guard_rejects_unknown_grn() -> None:
    case = load_e2e_case_catalog()["case_c_lora_guard_fallback"]
    values = e2e_case_values(case)

    assert values[2] == []
    assert case["guard_result"]["decision"] == "REJECT"
    assert "unknown_identifier:GRN-20260149" in str(values)
    assert "真实首轮离线 ModelScope 评测 artifact" in str(values)
    assert "Guard 未通过，已自动回退到确定性模板" in str(values)


def test_main_page_defaults_to_e2e_case_and_collapses_synthetic_cases() -> None:
    selector = _component_props("e2e-case-selector")
    synthetic = _component_props("synthetic-case-showcase")
    technical = _component_props("e2e-case-technical-details")

    assert selector["value"] == "case_a_standard_pass"
    assert len(selector["choices"]) == 3
    assert synthetic["open"] is False
    assert technical["open"] is False


def test_e2e_case_demo_smoke_is_ready() -> None:
    result = run_smoke()

    assert result["ready"] is True
    assert result["case_count"] == 3
    assert result["single_case_f1_claim"] is False
    assert result["model_weights_included"] is False
