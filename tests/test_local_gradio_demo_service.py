"""本地 Gradio Demo service 行为测试。"""

import pytest

from demo.demo_service import DemoService


def test_service_loads_unique_thirteen_cases():
    service = DemoService()

    assert len(service.case_ids) == 13
    assert len(service.case_ids) == len(set(service.case_ids))


def test_default_hybrid_template_output_is_complete():
    result = DemoService().run_case("normal_invoice")

    assert result.execution_path == "hybrid"
    assert result.static_fallback is False
    assert result.explanation_mode == "template"
    assert result.explanation_source == "template"
    assert result.used_rewrite is False
    assert result.raw_rewrite_output is None
    assert len(result.facts_hash) == 64
    assert result.audit_report["risk_level"] == "low"


def test_shadow_records_raw_rewrite_but_keeps_template():
    service = DemoService()
    template = service.run_case("normal_invoice", "template")
    shadow = service.run_case("normal_invoice", "shadow")

    assert shadow.explanation_source == "template"
    assert shadow.explanation_text == template.explanation_text
    assert shadow.used_rewrite is False
    assert shadow.guard_passed is True
    assert shadow.raw_rewrite_output == template.explanation_text
    assert shadow.fallback_reason == "shadow_mode_template_default"


@pytest.mark.parametrize(
    ("mode", "source", "fallback", "used_rewrite", "guard_passed"),
    [
        ("experimental_guard_pass", "controlled_rewrite", None, True, True),
        ("experimental_guard_fail", "template", "guard_failed", False, False),
        ("provider_runtime_error", "template", "model_runtime_error", False, False),
        ("invalid_output", "template", "invalid_lora_output", False, False),
    ],
)
def test_controlled_modes_fail_closed(
    mode, source, fallback, used_rewrite, guard_passed
):
    result = DemoService().run_case("normal_invoice", mode)

    assert result.explanation_source == source
    assert result.fallback_reason == fallback
    assert result.used_rewrite is used_rewrite
    assert result.guard_passed is guard_passed
    assert result.risk_level == "low"
    assert result.recommended_action == "auto_approve"
    assert result.anomaly_types == []


def test_high_risk_forces_template():
    result = DemoService().run_case(
        "high_risk_template_fallback", "experimental_guard_pass"
    )

    assert result.static_fallback is True
    assert result.risk_level == "high"
    assert result.recommended_action == "reject"
    assert result.anomaly_types == ["duplicate_invoice"]
    assert result.explanation_source == "template"
    assert result.fallback_reason == "high_risk_template_only"


def test_fixture_facts_are_preserved_in_static_fallback():
    service = DemoService()
    case = service._cases["amount_discrepancy"]
    result = service.run_case("amount_discrepancy")

    assert result.static_fallback is True
    assert result.risk_level == case["facts"]["risk_level"]
    assert result.recommended_action == case["facts"]["recommended_action"]
    assert result.anomaly_types == case["facts"]["anomaly_types"]
    assert result.evidence == case["facts"]["evidence"]
    assert result.missing_fields == case["facts"]["missing_fields"]


def test_runtime_failure_uses_static_fallback_without_escaping():
    def broken_runner(_case, _mode):
        raise RuntimeError("database unavailable")

    result = DemoService(hybrid_runner=broken_runner).run_case("normal_invoice")

    assert result.execution_path == "static_fallback"
    assert result.static_fallback is True
    assert result.static_fallback_reason == "hybrid_execution_unavailable"
    assert result.safe_error_summary == "RuntimeError: database unavailable"
    assert result.risk_level == "low"
    assert result.recommended_action == "auto_approve"
    assert result.anomaly_types == []
    assert result.audit_report["demo_metadata"]["execution_path"] == "static_fallback"


def test_default_mode_does_not_invoke_provider(monkeypatch):
    service = DemoService()

    def forbidden_provider(_request):
        raise AssertionError("template mode must not call provider")

    monkeypatch.setattr(service, "_passing_provider", forbidden_provider)

    result = service.run_case("normal_invoice", "template")

    assert result.explanation_source == "template"
    assert result.raw_rewrite_output is None
