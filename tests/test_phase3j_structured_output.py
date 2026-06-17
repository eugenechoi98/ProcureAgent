"""Phase 3J Structured Output First 离线闭环测试。"""

from pathlib import Path

import pytest

from procureguard.phase3.dataset import generate_samples
from procureguard.phase3.explanation import (
    CanonicalAuditFacts,
    DeterministicTemplateRenderer,
    StructuredExplanationRenderer,
    StructuredExplanationService,
    StructuredExplanationValidator,
    build_rule_only_structured_explanation,
)
from procureguard.phase3.structured_evaluation import (
    evaluate_structured_challenge_set,
    load_challenge_set,
    materialize_candidate,
)

FIXTURE = Path("tests/fixtures/phase3j_structured_challenge_set.json")


def _case(case_id: str):
    """读取指定 challenge case。"""

    challenge_set = load_challenge_set(FIXTURE)
    return next(item for item in challenge_set.cases if item.case_id == case_id)


def test_rule_only_schema_validator_and_renderer_pass():
    case = _case("p3j-004-rule-multi-pass")
    candidate = build_rule_only_structured_explanation(case.input_facts)

    validation, validated = StructuredExplanationValidator().validate(
        case.input_facts, candidate
    )
    text = StructuredExplanationRenderer().render(case.input_facts, validated)

    assert validation.passed is True
    assert validated is not None
    assert "缺少采购订单号" in text
    assert "发票金额不一致" in text
    assert f"风险等级：{case.input_facts.risk_level}" in text
    assert f"建议动作：{case.input_facts.recommended_action}" in text


def test_rule_only_baseline_accepts_all_existing_phase3_facts():
    service = StructuredExplanationService()

    for sample in generate_samples(42):
        facts = CanonicalAuditFacts.from_input_facts(sample.input_facts)
        candidate = build_rule_only_structured_explanation(facts)
        result = service.explain(facts, candidate)

        assert result.status == "accepted", (
            sample.sample_id,
            result.validation.reject_reasons,
            result.validation.unsupported_claims,
        )


@pytest.mark.parametrize(
    ("case_id", "claim_prefix"),
    [
        ("p3j-006-unknown-po", "unknown_identifier:PO-999999"),
        ("p3j-007-unknown-grn", "unknown_identifier:GRN-999999"),
        ("p3j-008-unknown-amount", "unknown_amount:999999.00"),
        ("p3j-009-unsupported-approver", "unsupported_policy_or_approver:审批人"),
        ("p3j-021-unknown-vendor", "unknown_vendor:Unknown Vendor LLC"),
    ],
)
def test_unknown_facts_and_approver_fail_closed(case_id, claim_prefix):
    case = _case(case_id)

    result = StructuredExplanationService().explain(
        case.input_facts, materialize_candidate(case)
    )

    assert result.status == "rejected"
    assert result.fallback_used is True
    assert any(
        item.startswith(claim_prefix) for item in result.validation.unsupported_claims
    )


@pytest.mark.parametrize(
    ("case_id", "reason"),
    [
        ("p3j-011-action-conflict", "recommended_action_copy_mismatch"),
        ("p3j-016-risk-conflict", "risk_level_copy_mismatch"),
        ("p3j-010-multi-anomaly-missing", "anomaly_types_missing"),
        ("p3j-015-extra-anomaly", "anomaly_types_extra"),
        ("p3j-017-missing-field-omitted", "missing_fields_omitted"),
        ("p3j-018-missing-field-extra", "missing_fields_extra"),
    ],
)
def test_decision_anomaly_and_missing_field_changes_are_rejected(case_id, reason):
    case = _case(case_id)

    result = StructuredExplanationService().explain(
        case.input_facts, materialize_candidate(case)
    )

    assert result.status == "rejected"
    assert reason in result.validation.reject_reasons


def test_invalid_evidence_id_and_claim_mismatch_are_rejected():
    invalid_id = _case("p3j-013-invalid-evidence-id")
    mismatch = _case("p3j-014-evidence-claim-mismatch")

    invalid_result = StructuredExplanationService().explain(
        invalid_id.input_facts, materialize_candidate(invalid_id)
    )
    mismatch_result = StructuredExplanationService().explain(
        mismatch.input_facts, materialize_candidate(mismatch)
    )

    assert invalid_result.validation.invalid_evidence_ids == ("evidence.999",)
    assert "invalid_evidence_ids" in invalid_result.validation.reject_reasons
    assert "evidence_claim_mismatch:bullet_1" in mismatch_result.validation.unsupported_claims


def test_renderer_rejects_unvalidated_input_and_facts_hash_mismatch():
    first = _case("p3j-001-rule-missing-po-pass")
    second = _case("p3j-002-rule-missing-grn-pass")
    candidate = build_rule_only_structured_explanation(first.input_facts)
    _, validated = StructuredExplanationValidator().validate(first.input_facts, candidate)
    renderer = StructuredExplanationRenderer()

    with pytest.raises(TypeError, match="ValidatedStructuredExplanation"):
        renderer.render(first.input_facts, candidate)
    with pytest.raises(ValueError, match="facts 不匹配"):
        renderer.render(second.input_facts, validated)


def test_schema_failure_and_semantic_failure_use_existing_template_fallback():
    schema_case = _case("p3j-020-schema-invalid")
    semantic_case = _case("p3j-011-action-conflict")
    service = StructuredExplanationService()
    template = DeterministicTemplateRenderer()

    for case in (schema_case, semantic_case):
        result = service.explain(case.input_facts, materialize_candidate(case))
        assert result.status == "rejected"
        assert result.fallback_used is True
        assert result.rendered_text == template.render(case.input_facts)


def test_evaluator_debug_report_has_required_metrics_and_rows():
    challenge_set = load_challenge_set(FIXTURE)

    report = evaluate_structured_challenge_set(challenge_set)

    required_metrics = {
        "json_validity",
        "schema_validity",
        "risk_level_exact_match",
        "recommended_action_exact_match",
        "anomaly_type_precision",
        "anomaly_type_recall",
        "missing_field_precision",
        "missing_field_recall",
        "evidence_id_precision",
        "evidence_id_recall",
        "unsupported_claim_rate",
    }
    required_row_fields = {
        "case_id",
        "expected_status",
        "actual_status",
        "failed_components",
        "unsupported_claims",
        "invalid_evidence_ids",
        "action_mismatch",
        "anomaly_missing_or_extra",
        "rendered_text_preview",
        "fallback_used",
    }
    assert len(challenge_set.cases) == 21
    assert challenge_set.training_data is False
    assert required_metrics <= set(report["metrics"])
    assert required_row_fields <= set(report["per_case_debug_rows"][0])
    assert report["metrics"]["expected_status_accuracy"] == 1.0
    assert report["metrics"]["fallback_accuracy"] == 1.0
    assert report["metrics"]["unsupported_claim_rate"] == 0.0
    assert report["baseline_passed"] is True
