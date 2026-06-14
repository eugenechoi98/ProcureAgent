"""发票案例演示的来源、展示边界和审核结果测试。"""

from __future__ import annotations

from pathlib import Path

from demo.app import build_app
from demo.demo_service import DemoService
from demo.invoice_case_view import load_invoice_case_catalog
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
        "invoice-case-extraction",
        "invoice-case-match",
        "invoice-case-evidence",
        "invoice-case-risk-action",
        "invoice-case-explanation",
    }

    for elem_id in expected:
        assert _component_props(elem_id)
    assert _component_props("invoice-audit-technical-output")["open"] is False


def test_invoice_case_smoke_is_ready() -> None:
    result = run_smoke()

    assert result["ready"] is True
    assert result["case_count"] == 5
    assert result["synthetic_images_only"] is True
    assert result["single_case_f1_claim"] is False
    assert result["layoutlmv3_live_inference"] is False
    assert result["real_lora_live_inference"] is False
