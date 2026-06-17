"""发票案例演示的来源、展示边界和审核结果测试。"""

from __future__ import annotations

from pathlib import Path

from demo.app import _path_b_preview, _run_for_ui, _run_path_b_scenario_for_ui, build_app
from demo.demo_service import DemoService
from demo.invoice_case_view import (
    EXPLANATION_MODE_LABELS,
    explanation_mode_choices,
    load_invoice_case_catalog,
    preview_values,
    render_case_summary,
)
from demo.scenario_registry import SCENARIO_REGISTRY, get_scenario
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


def test_path_b_interactive_flow_sections_are_visible() -> None:
    expected = {
        "invoice-case-image",
        "invoice-case-extraction",
        "main-ocr-result",
        "main-risk-card",
        "main-action-card",
        "main-final-explanation",
        "case-validation-summary",
        "run-audit-button",
        "case-explanation-mode-selector",
    }

    for elem_id in expected:
        assert _component_props(elem_id)
    assert _component_props("path-a-tab")
    assert _component_props("path-b-tab")
    assert _component_props("system-explanation-tab")
    try:
        _component_props("explanation-layer-tab")
    except AssertionError:
        pass
    else:
        raise AssertionError("LoRA explanation must not be a standalone tab")


def test_main_chain_copy_is_interview_friendly() -> None:
    rendered = "\n".join(
        str(component.get("props", {}).get("value", ""))
        for component in build_app().get_config_file()["components"]
        if component.get("type") == "markdown"
    )

    assert "Path B 展示发票图片到 AuditReport 的完整交互链路" in rendered
    assert "预置场景流程演示" in rendered
    assert "Run Audit 会按 OCR预置结果" in rendered
    assert "不执行实时 OCR 或模型推理" in rendered


def test_explanation_modes_use_chinese_labels_and_stable_internal_values() -> None:
    service = DemoService()
    choices = explanation_mode_choices(service.explanation_modes)

    assert [value for _, value in choices] == service.explanation_modes
    assert dict((value, label) for label, value in choices) == (
        EXPLANATION_MODE_LABELS
    )
    selector = _component_props("case-explanation-mode-selector")
    selector_values = [
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in selector["choices"]
    ]
    assert selector_values == ["LoRA OFF", "LoRA ON"]
    assert selector["value"] == "LoRA OFF"


def test_invoice_run_status_is_visible_and_completed_output_is_concise() -> None:
    catalog = load_invoice_case_catalog()
    service = DemoService()

    output = _run_for_ui(
        service,
        catalog,
        "vendor_name_mismatch",
        "experimental_guard_fail",
    )
    completed_status = output[2]
    assert "审核状态：已完成" in completed_status
    assert catalog["vendor_name_mismatch"]["display_name"] in completed_status
    assert "中风险" in completed_status
    assert "转人工审批" in completed_status
    assert "Guard 拦截后回退到确定性模板" in completed_status
    assert output[0] == catalog["vendor_name_mismatch"]["match_rows"]
    assert output[1] == catalog["vendor_name_mismatch"]["evidence_rows"]


def test_case_preview_does_not_prepopulate_audit_results() -> None:
    catalog = load_invoice_case_catalog()

    for case_id in catalog:
        preview = preview_values(catalog, case_id)
        assert preview[4] == [
            ["审核状态", "尚未运行", "点击“运行审核”后生成"]
        ]
        assert preview[5] == [
            ["审核状态", "尚未运行", "点击“运行审核”后生成"]
        ]
        assert "审核结果：** 尚未运行" in preview[6]
        assert "正式解释：** 尚未运行" in preview[7]


def test_path_b_preview_and_run_follow_preset_scenario_flow() -> None:
    catalog = load_invoice_case_catalog()

    preview = _path_b_preview(catalog, "normal_invoice")
    assert preview[3] == []
    assert preview[4] == {}
    assert preview[10] == ""
    assert preview[11] == ""
    assert "未运行" in preview[7]

    output = _run_path_b_scenario_for_ui(catalog, "normal_invoice", "LoRA OFF")
    trace = output[5]
    ocr_json = output[10]
    assert trace["execution_id"].startswith("exec_")
    assert ocr_json["execution_id"] == trace["execution_id"]
    assert trace["status"] == "已完成审计"
    assert trace["state_sequence"] == ["已加载", "已展示OCR", "已完成审计"]
    assert trace["scenario_source"] == "scenario_registry"
    assert trace["realtime_ocr"] is False
    assert ocr_json["state"] == "已展示OCR"
    assert all(item["value"] for item in ocr_json["fields"])
    assert output[1] == "低风险"
    assert output[2] == "自动通过"
    assert len(output[9]) == 7
    assert output[9][0][1] == "INV-2505-1001"
    assert "scenario_001" in output[4]
    assert "确定性规则审计" in output[4]

    lora_output = _run_path_b_scenario_for_ui(catalog, "normal_invoice", "LoRA ON")
    assert lora_output[5]["lora_mode"] == "LoRA ON"
    assert "多维度规则核验" in lora_output[4]
    assert lora_output[1:3] == output[1:3]


def test_all_scenarios_have_complete_non_null_ocr_fields() -> None:
    required = {
        "invoice_number",
        "po_number",
        "grn_number",
        "total_amount",
        "vendor_name",
        "date",
        "item_list",
    }
    scenario_ids = set()

    for case_id, scenario in SCENARIO_REGISTRY.items():
        scenario_ids.add(scenario.scenario_id)
        assert scenario.image_path.endswith(".png")
        fields = scenario.fields
        assert set(fields) == required, case_id
        assert all(value not in ("", None) for value in fields.values())
        assert not any(str(value).startswith("NO_") for value in fields.values())
    assert len(scenario_ids) == len(SCENARIO_REGISTRY)


def test_all_scenario_runs_use_complete_bound_fields_and_case_outcomes() -> None:
    catalog = load_invoice_case_catalog()

    forbidden = {"缺失", "未提供"}
    failing_cases = {"vendor_name_mismatch", "duplicate_invoice"}
    for case_id in catalog:
        output = _run_path_b_scenario_for_ui(catalog, case_id, "LoRA OFF")
        scenario = get_scenario(case_id)
        rule_rows = output[7]
        field_rows = output[9]
        if case_id in failing_cases:
            assert any(row[2] == "FALSE" for row in rule_rows)
            assert output[1] == "高风险"
            assert output[2] == "拒绝"
            assert output[6]["audit_result"] == "not_pass"
        else:
            assert all(row[2] == "TRUE" for row in rule_rows)
            assert output[6]["audit_result"] == "pass"
        assert all(row[1] not in forbidden for row in field_rows)
        assert not any(str(row[1]).startswith("NO_") for row in field_rows)
        assert output[5]["scenario_id"] == scenario.scenario_id
        assert output[5]["image_scenario_id"] == scenario.scenario_id
        assert output[5]["ocr_scenario_id"] == scenario.scenario_id
        assert output[5]["audit_scenario_id"] == scenario.scenario_id


def test_pre_audit_preview_has_no_mismatch_or_warning_flags() -> None:
    catalog = load_invoice_case_catalog()
    forbidden = {
        "mismatch",
        "warning",
        "duplicate",
        "high risk",
        "不一致",
        "高风险",
        "重复",
        "缺失",
    }

    for case_id in catalog:
        preview = _path_b_preview(catalog, case_id)
        rendered = " ".join(str(item).lower() for item in preview[:3])
        assert not any(flag in rendered for flag in forbidden), case_id


def test_path_b_ui_has_no_local_scenario_hardcode() -> None:
    source = Path("demo/app.py").read_text(encoding="utf-8")

    assert "SCENARIO_MAP" not in source
    assert "SCENARIO_FIELD_LABELS" not in source
    assert "FIELD_CONFIDENCES" not in source


def test_each_case_summary_explains_the_governance_path() -> None:
    catalog = load_invoice_case_catalog()

    for case in catalog.values():
        summary = render_case_summary(case)
        assert "解释路径" in summary
        assert "scenario" in case["summary"] or "确定性模板" in summary

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
