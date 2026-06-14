"""发票案例演示的来源、展示边界和审核结果测试。"""

from __future__ import annotations

from pathlib import Path

from demo.app import _run_for_ui, build_app
from demo.demo_service import DemoService
from demo.invoice_case_view import (
    EXPLANATION_MODE_LABELS,
    explanation_mode_choices,
    load_invoice_case_catalog,
    render_case_summary,
)
from scripts.demo.run_invoice_case_demo_smoke import run_smoke


def _component_props(elem_id: str) -> dict:
    components = build_app().get_config_file()["components"]
    for component in components:
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props
    raise AssertionError(f"Missing component elem_id={elem_id}")


def test_catalog_contains_five_synthetic_public_demo_cases() -> None:
    catalog = load_invoice_case_catalog()

    assert list(catalog) == [
        "normal_invoice",
        "missing_goods_receipt",
        "missing_po_number",
        "vendor_name_mismatch",
        "duplicate_invoice",
    ]
    assert {case["risk_level"] for case in catalog.values()} == {
        "low",
        "medium",
        "high",
    }
    for case in catalog.values():
        assert case["source_type"] == "synthetic_imagegen"
        assert "不是" in case["scope_note"]
        assert "不证明" in case["scope_note"]
        assert case["summary"]


def test_case_images_exist_and_are_lightweight_png_files() -> None:
    catalog = load_invoice_case_catalog()

    for case in catalog.values():
        image_path = Path(__file__).resolve().parents[1] / "demo" / case["image"]
        assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert image_path.stat().st_size < 1_000_000


def test_extraction_comparison_does_not_claim_single_image_inference() -> None:
    catalog = load_invoice_case_catalog()

    for case in catalog.values():
        for row in case["extraction_rows"]:
            if row[2] == "不适用":
                assert row[3] == "不适用"
            else:
                assert row[2:4] == ["未运行", "未运行"]


def test_existing_demo_service_results_match_case_story() -> None:
    catalog = load_invoice_case_catalog()
    service = DemoService()

    for case_id, case in catalog.items():
        result = service.run_case(case_id, case["recommended_mode"])

        assert result.risk_level == case["risk_level"]
        assert result.recommended_action == case["recommended_action"]


def test_guard_and_fallback_story_uses_controlled_demo_providers() -> None:
    catalog = load_invoice_case_catalog()
    service = DemoService()

    guard_case = service.run_case(
        "vendor_name_mismatch",
        catalog["vendor_name_mismatch"]["recommended_mode"],
    )
    high_risk_case = service.run_case(
        "duplicate_invoice",
        catalog["duplicate_invoice"]["recommended_mode"],
    )

    assert guard_case.explanation_source == "template"
    assert guard_case.guard_passed is False
    assert guard_case.fallback_reason == "guard_failed"
    assert high_risk_case.explanation_source == "template"
    assert high_risk_case.fallback_reason == "high_risk_template_only"


def test_invoice_tab_has_exactly_six_case_showcase_sections() -> None:
    expected = {
        "invoice-case-image",
        "invoice-case-brief",
        "invoice-case-image-note",
        "invoice-case-extraction",
        "invoice-case-match",
        "invoice-case-evidence",
        "invoice-case-risk-action",
        "invoice-case-explanation",
    }

    for elem_id in expected:
        assert _component_props(elem_id)
    assert _component_props("invoice-audit-technical-output")["open"] is False


def test_invoice_case_brief_and_metric_note_are_visible() -> None:
    brief = _component_props("invoice-case-brief")["value"]
    image_note = _component_props("invoice-case-image-note")["value"]
    metric_note = _component_props("invoice-case-f1-note")["value"]

    assert "正常标准发票" in brief
    assert "低风险" in brief
    assert "演示用合成示意图" in image_note
    assert "不代表单图模型评测结论" in image_note
    assert "整体 F1 指标请见“模型实验”页" in metric_note


def test_explanation_modes_use_chinese_labels_and_stable_internal_values() -> None:
    service = DemoService()
    choices = explanation_mode_choices(service.explanation_modes)

    assert [value for _, value in choices] == service.explanation_modes
    assert dict((value, label) for label, value in choices) == (
        EXPLANATION_MODE_LABELS
    )
    selector = _component_props("explanation-mode-selector")
    assert selector["choices"] == choices
    assert selector["value"] == "template"


def test_invoice_run_status_is_visible_and_completed_output_is_concise() -> None:
    catalog = load_invoice_case_catalog()
    service = DemoService()
    initial_status = _component_props("invoice-run-status")["value"]

    assert "审核状态：待运行" in initial_status
    output = _run_for_ui(
        service,
        catalog,
        "vendor_name_mismatch",
        "experimental_guard_fail",
    )
    completed_status = output[0]
    assert "审核状态：已完成" in completed_status
    assert catalog["vendor_name_mismatch"]["display_name"] in completed_status
    assert "中风险" in completed_status
    assert "转人工审批" in completed_status
    assert "Guard 拦截后回退到确定性模板" in completed_status


def test_each_case_summary_explains_the_governance_path() -> None:
    catalog = load_invoice_case_catalog()

    for case in catalog.values():
        summary = render_case_summary(case)
        assert "解释路径" in summary
        assert "确定性模板" in summary

    assert "Guard 拦截" in render_case_summary(
        catalog["vendor_name_mismatch"]
    )


def test_invoice_case_smoke_is_ready() -> None:
    result = run_smoke()

    assert result["ready"] is True
    assert result["case_count"] == 5
    assert result["synthetic_images_only"] is True
    assert result["single_case_f1_claim"] is False
    assert result["layoutlmv3_live_inference"] is False
    assert result["real_lora_live_inference"] is False
