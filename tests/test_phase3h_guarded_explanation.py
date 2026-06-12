"""Phase 3H 受控解释层最小闭环测试。"""

from procureguard.phase3.dataset import generate_samples
from procureguard.phase3.explanation import (
    CanonicalAuditFacts,
    DeterministicTemplateRenderer,
    FallbackOrchestrator,
    LoRAOutputGuard,
    RewriteRequest,
    RewriteResponse,
    build_rewrite_prompt,
)
from procureguard.phase3.schemas import AnomalyType


def _facts_for(anomaly_type: AnomalyType) -> CanonicalAuditFacts:
    """从固定 synthetic 样本构造 Canonical Audit Facts。"""

    sample = next(
        item for item in generate_samples(42) if item.anomaly_type == anomaly_type
    )
    return CanonicalAuditFacts.from_input_facts(
        sample.input_facts, invoice_id=sample.sample_id
    )


def test_template_renderer_is_deterministic_and_traceable():
    facts = _facts_for(AnomalyType.AMOUNT_DISCREPANCY)
    renderer = DeterministicTemplateRenderer()

    first = renderer.render(facts)
    second = renderer.render(facts)

    assert first == second
    assert "审核摘要：" in first
    assert "异常类型：" in first
    assert "发票金额不一致" in first
    assert f"风险等级：{facts.risk_level}" in first
    assert f"建议动作：{facts.recommended_action}" in first
    assert len(facts.facts_hash()) == 64


def test_all_deterministic_templates_pass_output_guard():
    renderer = DeterministicTemplateRenderer()
    guard = LoRAOutputGuard()

    for sample in generate_samples(42):
        facts = CanonicalAuditFacts.from_input_facts(sample.input_facts)
        result = guard.verify(facts, renderer.render(facts))

        assert result.passed is True, (sample.sample_id, result.violations)


def test_controlled_rewrite_prompt_keeps_contract_boundaries():
    facts = _facts_for(AnomalyType.MISSING_PO_NUMBER)
    template = DeterministicTemplateRenderer().render(facts)
    request = RewriteRequest(facts=facts, template_output=template)

    prompt = build_rewrite_prompt(request)

    assert "Canonical Audit Facts" in prompt
    assert "Template Output" in prompt
    assert "不得改变 risk_level" in prompt
    assert "必须保留模板中的固定章节标题" in prompt


def test_guard_rejects_unknown_facts_changed_action_and_missing_sections():
    facts = _facts_for(AnomalyType.MISSING_GOODS_RECEIPT)
    output = (
        "审核摘要：模型补了未知事实。\n"
        "异常类型：缺少收货记录\n"
        "关键证据：供应商 Unknown Vendor LLC；发票号 INV-99999999；"
        "收货单号 GRN-unknown；发票金额 USD 999999.00。\n"
        "风险等级：low\n"
        "建议动作：auto_approve\n"
        "交由 CFO 根据政策第 9 条审批。"
    )

    result = LoRAOutputGuard().verify(facts, output)

    assert result.passed is False
    assert "missing_section:缺失字段：" in result.violations
    assert any(item.startswith("unknown_identifier:INV-99999999") for item in result.violations)
    assert any(item.startswith("unknown_identifier:GRN-unknown") for item in result.violations)
    assert any(item.startswith("unknown_amount:999999.00") for item in result.violations)
    assert any(item.startswith("unknown_vendor:Unknown Vendor LLC") for item in result.violations)
    assert any(item.startswith("changed_risk_level") for item in result.violations)
    assert any(item.startswith("changed_recommended_action") for item in result.violations)
    assert any("CFO" in item for item in result.violations)


def test_orchestrator_uses_template_by_default_and_shadow_records_raw_output():
    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    orchestrator = FallbackOrchestrator()
    template_result = orchestrator.explain(facts)

    def provider(request: RewriteRequest) -> RewriteResponse:
        return RewriteResponse(
            raw_text=request.template_output,
            model_version="qwen2.5-0.5b",
            adapter_version="phase3g-second",
        )

    shadow_result = orchestrator.explain(facts, mode="shadow", rewrite_provider=provider)

    assert template_result.used_rewrite is False
    assert template_result.audit_trail.fallback_reason == "mvp_template_default"
    assert shadow_result.used_rewrite is False
    assert shadow_result.explanation == template_result.explanation
    assert shadow_result.audit_trail.raw_llm_output == template_result.explanation
    assert shadow_result.audit_trail.fallback_reason == "shadow_mode_template_default"
    assert shadow_result.audit_trail.model_version == "qwen2.5-0.5b"


def test_experimental_rewrite_can_be_used_only_after_guard_passes():
    facts = _facts_for(AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED)
    orchestrator = FallbackOrchestrator()
    template = DeterministicTemplateRenderer().render(facts)

    def provider(_: RewriteRequest) -> str:
        return template

    result = orchestrator.explain(
        facts, mode="experimental", rewrite_provider=provider
    )

    assert result.used_rewrite is True
    assert result.explanation == template
    assert result.audit_trail.fallback_reason is None
    assert result.audit_trail.verifier_result.passed is True


def test_high_risk_never_uses_rewrite_even_if_guard_would_pass():
    facts = _facts_for(AnomalyType.DUPLICATE_INVOICE)
    orchestrator = FallbackOrchestrator()

    def provider(_: RewriteRequest) -> str:
        raise AssertionError("高风险不应调用重写模型")

    result = orchestrator.explain(
        facts, mode="experimental", rewrite_provider=provider
    )

    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == "high_risk_template_only"
    assert "重复发票" in result.explanation
