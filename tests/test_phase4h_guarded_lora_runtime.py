"""Phase 4H Guarded LoRA rewrite runtime 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.phase3.dataset import generate_samples
from procureguard.phase3.explanation import (
    CanonicalAuditFacts,
    DeterministicTemplateRenderer,
    FallbackOrchestrator,
)
from procureguard.phase3.explanation.rewrite_contract import RewriteRequest, RewriteResponse
from procureguard.phase3.schemas import AnomalyType
from procureguard.productization.e2e_audit import ExecuteAuditRequest, execute_audit_pipeline
from tests.test_phase4g_ext_e2e_pipeline import candidate_payload


def _facts() -> CanonicalAuditFacts:
    """构造包含 PO/GRN/供应商/金额/日期的固定事实。"""

    sample = next(
        item for item in generate_samples(42) if item.anomaly_type == AnomalyType.QUANTITY_MISMATCH
    )
    return CanonicalAuditFacts.from_input_facts(
        sample.input_facts, invoice_id=sample.sample_id
    ).model_copy(update={"invoice_date": "2026-06-17"})


def _template(facts: CanonicalAuditFacts) -> str:
    """渲染安全基线模板。"""

    return DeterministicTemplateRenderer().render(facts)


def test_template_mode_does_not_call_lora_provider() -> None:
    facts = _facts()

    def provider(_request: RewriteRequest) -> str:
        raise AssertionError("template mode must not call LoRA provider")

    result = FallbackOrchestrator().explain(
        facts, mode="template", rewrite_provider=provider
    )

    assert result.explanation == _template(facts)
    assert result.used_rewrite is False
    assert result.audit_trail.final_source == "template"


def test_guarded_lora_provider_unavailable_falls_back_template() -> None:
    facts = _facts()
    result = FallbackOrchestrator().explain(facts, mode="guarded_lora")

    assert result.explanation == _template(facts)
    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == "provider_unavailable"
    assert result.audit_trail.final_source == "fallback"


def test_guarded_lora_empty_output_falls_back_template() -> None:
    facts = _facts()

    result = FallbackOrchestrator().explain(
        facts,
        mode="guarded_lora",
        rewrite_provider=lambda _request: RewriteResponse(
            raw_text="",
            provider_name="fake_test_provider",
            model_version="fake-model",
            adapter_version="fake-adapter",
            latency_ms=1.0,
        ),
    )

    assert result.explanation == _template(facts)
    assert result.audit_trail.fallback_reason == "empty_lora_output"
    assert result.audit_trail.provider_name == "fake_test_provider"


@pytest.mark.parametrize(
    ("mutator", "violation_prefix"),
    [
        (lambda text, facts: text.replace(facts.po_number, "PO-UNKNOWN-999"), "unknown_identifier:PO-UNKNOWN-999"),
        (lambda text, facts: text.replace(facts.grn_number, "GRN-UNKNOWN-999"), "unknown_identifier:GRN-UNKNOWN-999"),
        (lambda text, _facts: text + "\n补充金额 USD 999999.99", "unknown_amount:999999.99"),
        (
            lambda text, facts: text.replace(
                f"供应商 {facts.vendor_name}", "供应商 Imaginary Vendor"
            ),
            "unknown_vendor:Imaginary Vendor",
        ),
        (lambda text, _facts: text.replace("2026-06-17", "2026-06-18"), "unknown_date:2026-06-18"),
        (lambda text, _facts: text.replace("风险等级：medium", "风险等级：high"), "changed_risk_level:high"),
        (
            lambda text, _facts: text.replace(
                "建议动作：request_human_approval", "建议动作：auto_approve"
            ),
            "changed_recommended_action:auto_approve",
        ),
        (lambda text, _facts: text.replace("收货数量不一致", "未说明"), "missing_anomaly_type:收货数量不一致"),
        (lambda text, _facts: text + "\n审批人 CFO 已确认。", "unsupported_policy_or_approver:CFO"),
        (lambda text, _facts: text + "\n结论：可以立即付款。", "forbidden_claim:立即付款"),
    ],
)
def test_guard_rejects_fact_decision_and_forbidden_claim_mutations(
    mutator, violation_prefix: str
) -> None:
    facts = _facts()
    unsafe = mutator(_template(facts), facts)

    result = FallbackOrchestrator().explain(
        facts,
        mode="guarded_lora",
        rewrite_provider=lambda _request: RewriteResponse(
            raw_text=unsafe,
            provider_name="fake_test_provider",
            model_version="fake-model",
            adapter_version="fake-adapter",
        ),
    )

    assert result.explanation == _template(facts)
    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == "guard_failed"
    assert any(item.startswith(violation_prefix) for item in result.audit_trail.verifier_result.violations)
    assert result.audit_trail.verifier_result.violation_details


def test_missing_field_completion_is_rejected() -> None:
    facts = _facts().model_copy(update={"po_number": None, "missing_fields": ("po_number",)})
    unsafe = _template(facts).replace("po_number：未提供（缺失）", "po_number：PO-FILLED-001")

    result = FallbackOrchestrator().explain(
        facts,
        mode="guarded_lora",
        rewrite_provider=lambda _request: unsafe,
    )

    assert result.used_rewrite is False
    assert "missing_field_completion:po_number" in result.audit_trail.verifier_result.violations


def test_guard_pass_uses_lora_rewrite_and_records_trace_hashes() -> None:
    facts = _facts()
    rewrite = _template(facts)

    result = FallbackOrchestrator().explain(
        facts,
        mode="guarded_lora",
        rewrite_provider=lambda _request: RewriteResponse(
            raw_text=rewrite,
            provider_name="fake_test_provider",
            model_version="fake-model",
            adapter_version="fake-adapter",
            latency_ms=2.5,
        ),
    )

    assert result.used_rewrite is True
    assert result.explanation == rewrite
    assert result.audit_trail.final_source == "lora"
    assert result.audit_trail.template_hash
    assert result.audit_trail.lora_candidate_hash
    assert result.audit_trail.provider_name == "fake_test_provider"
    assert result.audit_trail.latency_ms == 2.5


def test_shadow_lora_never_changes_final_output_even_when_guard_passes() -> None:
    facts = _facts()
    template = _template(facts)

    result = FallbackOrchestrator().explain(
        facts,
        mode="shadow_lora",
        rewrite_provider=lambda _request: template,
    )

    assert result.used_rewrite is False
    assert result.explanation == template
    assert result.audit_trail.fallback_reason == "shadow_mode_template_default"
    assert result.audit_trail.final_source == "template"


def test_4g_ext_guarded_lora_provider_unavailable_keeps_rules_decision() -> None:
    request = ExecuteAuditRequest.model_validate(
        {**candidate_payload(), "explanation_mode": "guarded_lora"}
    )
    result = execute_audit_pipeline(request)

    assert result.json["audit_report"]["risk_level"] == "low"
    assert result.json["audit_report"]["recommended_action"] == "auto_approve"
    assert result.trace.guard_status == "failed_fallback"
    assert result.trace.fallback_reason == "provider_unavailable"
    assert result.trace.risk_level_origin == "rules_only"
    assert result.trace.recommended_action_origin == "rules_only"


def test_api_execute_template_mode_still_passes(tmp_path) -> None:
    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/mvp/audit/execute", json=candidate_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["trace"]["guard_status"] == "not_used"
    assert body["json"]["audit_report"]["risk_level"] == "low"
