"""Phase 3H 受控解释层最小闭环测试。"""

import pytest
from pydantic import ValidationError

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


def test_canonical_facts_hash_changes_with_facts_and_json_stays_serializable():
    first = _facts_for(AnomalyType.AMOUNT_DISCREPANCY)
    second = _facts_for(AnomalyType.QUANTITY_MISMATCH)

    assert first.facts_hash() == first.facts_hash()
    assert first.facts_hash() != second.facts_hash()
    payload = first.model_dump(mode="json")
    assert isinstance(payload["evidence"], list)
    assert isinstance(first.model_dump_json(), str)


def test_canonical_facts_are_deeply_immutable_and_defensively_copied():
    anomaly_types = [AnomalyType.QUANTITY_MISMATCH]
    missing_fields = ["po_number"]
    policy_flags = ["manual_review_required"]
    evidence = [
        {
            "field": "custom",
            "nested": {"items": [1, {"value": "original"}]},
        }
    ]
    facts = CanonicalAuditFacts(
        anomaly_types=anomaly_types,
        missing_fields=missing_fields,
        policy_flags=policy_flags,
        evidence=evidence,
        risk_level="medium",
        recommended_action="request_human_approval",
    )

    anomaly_types.append(AnomalyType.DUPLICATE_INVOICE)
    missing_fields.clear()
    policy_flags.append("external_change")
    evidence[0]["nested"]["items"][1]["value"] = "changed"

    assert facts.anomaly_types == (AnomalyType.QUANTITY_MISMATCH,)
    assert facts.missing_fields == ("po_number",)
    assert facts.policy_flags == ("manual_review_required",)
    assert facts.evidence[0]["nested"]["items"][1]["value"] == "original"

    with pytest.raises(ValidationError):
        facts.risk_level = "high"
    with pytest.raises(ValidationError):
        facts.recommended_action = "reject"
    for value in (
        facts.anomaly_types,
        facts.missing_fields,
        facts.policy_flags,
        facts.evidence,
    ):
        with pytest.raises(AttributeError):
            value.append("blocked")
        with pytest.raises(AttributeError):
            value.remove(value[0])
    with pytest.raises(TypeError):
        facts.anomaly_types[0] = AnomalyType.DUPLICATE_INVOICE
    with pytest.raises(TypeError):
        facts.evidence[0]["nested"] = {}
    with pytest.raises(TypeError):
        facts.evidence[0]["nested"]["items"][1]["value"] = "blocked"
    with pytest.raises(TypeError):
        facts.evidence[0]["nested"]["items"][0] = 2


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


@pytest.mark.parametrize(
    ("anomaly_type", "mutate", "violation_prefix"),
    [
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda facts, text: text.replace(facts.po_number, "PO-999999"),
            "unknown_identifier:PO-999999",
        ),
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda facts, text: text.replace(facts.grn_number, "GRN-999999"),
            "unknown_identifier:GRN-999999",
        ),
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda facts, text: text.replace(facts.invoice_number, "INV-999999"),
            "unknown_identifier:INV-999999",
        ),
        (
            AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED,
            lambda facts, text: text.replace(
                f"{facts.currency} {facts.total_amount:.2f}",
                f"{facts.currency} 999999.00",
            ),
            "unknown_amount:999999.00",
        ),
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda facts, text: text.replace(
                f"供应商 {facts.vendor_name}", "供应商 Unknown Vendor LLC"
            ),
            "unknown_vendor:Unknown Vendor LLC",
        ),
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda _facts, text: text + "\n依据政策第 99 条处理。",
            "unsupported_policy_or_approver:政策第",
        ),
        (
            AnomalyType.QUANTITY_MISMATCH,
            lambda _facts, text: text + "\n交由 CFO 审批。",
            "unsupported_policy_or_approver:CFO",
        ),
    ],
)
def test_guard_rejects_each_declared_unknown_fact(
    anomaly_type, mutate, violation_prefix
):
    facts = _facts_for(anomaly_type)
    template = DeterministicTemplateRenderer().render(facts)

    result = LoRAOutputGuard().verify(facts, mutate(facts, template))

    assert result.passed is False
    assert any(item.startswith(violation_prefix) for item in result.violations)


def test_guard_rejects_added_or_removed_anomaly_and_changed_decisions():
    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    template = DeterministicTemplateRenderer().render(facts)
    guard = LoRAOutputGuard()

    added = guard.verify(facts, template + "\n补充异常：重复发票")
    removed = guard.verify(facts, template.replace("收货数量不一致", "未说明"))
    changed_risk = guard.verify(
        facts, template.replace("风险等级：medium", "风险等级：high")
    )
    changed_action = guard.verify(
        facts,
        template.replace(
            "建议动作：request_human_approval", "建议动作：auto_approve"
        ),
    )
    missing_section = guard.verify(
        facts,
        "\n".join(
            line for line in template.splitlines() if not line.startswith("缺失字段：")
        ),
    )

    assert any(item.startswith("unknown_anomaly_type") for item in added.violations)
    assert any(item.startswith("missing_anomaly_type") for item in removed.violations)
    assert any(item.startswith("changed_risk_level") for item in changed_risk.violations)
    assert any(
        item.startswith("changed_recommended_action")
        for item in changed_action.violations
    )
    assert "missing_section:缺失字段：" in missing_section.violations


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
    assert shadow_result.audit_trail.adapter_version == "phase3g-second"
    assert shadow_result.audit_trail.verifier_result.passed is True


@pytest.mark.parametrize(
    ("provider", "reason", "raw_output"),
    [
        (lambda _request: "", "empty_lora_output", ""),
        (lambda _request: None, "empty_lora_output", None),
        (lambda _request: 123, "invalid_lora_output", "123"),
        (
            lambda _request: object(),
            "invalid_lora_output",
            "<object object at",
        ),
        (
            lambda _request: {"raw_text": None},
            "rewrite_parse_error",
            '"raw_text": null',
        ),
    ],
)
def test_invalid_rewrite_outputs_fail_closed(provider, reason, raw_output):
    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    template = DeterministicTemplateRenderer().render(facts)

    result = FallbackOrchestrator().explain(
        facts, mode="experimental", rewrite_provider=provider
    )

    assert result.explanation == template
    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == reason
    assert result.audit_trail.verifier_result.passed is False
    if raw_output is None:
        assert result.audit_trail.raw_llm_output is None
    else:
        assert raw_output in result.audit_trail.raw_llm_output


def test_lora_unavailable_validation_error_and_runtime_error_fail_closed():
    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    orchestrator = FallbackOrchestrator()

    unavailable = orchestrator.explain(facts, mode="experimental")

    def validation_error_provider(_request: RewriteRequest):
        return RewriteResponse.model_validate({"raw_text": None})

    validation_error = orchestrator.explain(
        facts, mode="experimental", rewrite_provider=validation_error_provider
    )

    def runtime_error_provider(_request: RewriteRequest):
        raise RuntimeError("model failed")

    runtime_error = orchestrator.explain(
        facts, mode="experimental", rewrite_provider=runtime_error_provider
    )

    assert unavailable.audit_trail.fallback_reason == "lora_unavailable"
    assert validation_error.audit_trail.fallback_reason == "rewrite_parse_error"
    assert runtime_error.audit_trail.fallback_reason == "model_runtime_error"
    assert all(
        result.used_rewrite is False
        for result in (unavailable, validation_error, runtime_error)
    )


def test_hostile_invalid_object_cannot_escape_fail_closed_fallback():
    class HostileOutput:
        def __eq__(self, _other):
            raise RuntimeError("comparison failed")

        def __repr__(self):
            raise RuntimeError("representation failed")

    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    result = FallbackOrchestrator().explain(
        facts,
        mode="experimental",
        rewrite_provider=lambda _request: HostileOutput(),
    )

    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == "invalid_lora_output"
    assert result.audit_trail.raw_llm_output == "<unrepresentable:HostileOutput>"


def test_guard_exception_fails_closed_and_records_raw_output():
    class BrokenGuard:
        def verify(self, _facts, _output):
            raise ValueError("cannot parse guard input")

    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    template = DeterministicTemplateRenderer().render(facts)
    result = FallbackOrchestrator(guard=BrokenGuard()).explain(
        facts,
        mode="experimental",
        rewrite_provider=lambda _request: RewriteResponse(
            raw_text=template,
            model_version="test-model",
            adapter_version="test-adapter",
        ),
    )

    assert result.explanation == template
    assert result.used_rewrite is False
    assert result.audit_trail.fallback_reason == "guard_parse_error"
    assert result.audit_trail.raw_llm_output == template
    assert result.audit_trail.model_version == "test-model"
    assert result.audit_trail.adapter_version == "test-adapter"
    assert result.audit_trail.verifier_result.passed is False


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
    assert result.audit_trail.facts_hash == facts.facts_hash()
    assert result.audit_trail.template_version == "phase3h-template-v1"
    assert result.audit_trail.prompt_version == "phase3h-controlled-rewrite-v1"


def test_experimental_guard_failure_records_versions_raw_output_and_fallback():
    facts = _facts_for(AnomalyType.QUANTITY_MISMATCH)
    template = DeterministicTemplateRenderer().render(facts)
    unsafe = template.replace(facts.invoice_number, "INV-999999")

    result = FallbackOrchestrator().explain(
        facts,
        mode="experimental",
        rewrite_provider=lambda _request: RewriteResponse(
            raw_text=unsafe,
            model_version="test-model",
            adapter_version="test-adapter",
        ),
    )

    assert result.used_rewrite is False
    assert result.explanation == template
    assert result.audit_trail.fallback_reason == "guard_failed"
    assert result.audit_trail.raw_llm_output == unsafe
    assert result.audit_trail.model_version == "test-model"
    assert result.audit_trail.adapter_version == "test-adapter"
    assert result.audit_trail.verifier_result.passed is False


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
