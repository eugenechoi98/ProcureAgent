"""Phase 3K evidence citation 离线闭环测试。"""

from pathlib import Path

import pytest

from procureguard.phase3.citation_evaluation import (
    evaluate_citation_challenge_set,
    load_citation_challenge_set,
    materialize_citation_case,
)
from procureguard.phase3.explanation import (
    CitationExplanationService,
    CitationRenderer,
    ClaimEvidenceValidator,
    DeterministicTemplateRenderer,
    build_rule_only_citation_explanation,
)

FIXTURE = Path("tests/fixtures/phase3k_citation_challenge_set.json")


def _case(case_id: str):
    """取得固定 citation challenge。"""

    return next(
        item
        for item in load_citation_challenge_set(FIXTURE).cases
        if item.case_id == case_id
    )


def _result(case_id: str):
    """运行指定挑战案例。"""

    case = _case(case_id)
    catalog, payload = materialize_citation_case(case)
    return case, catalog, payload, CitationExplanationService().explain(
        case.input_facts, catalog, payload
    )


@pytest.mark.parametrize(
    "case_id",
    [
        "p3k-001-valid-po-amount",
        "p3k-002-valid-grn-missing",
        "p3k-003-valid-duplicate",
        "p3k-004-valid-policy",
        "p3k-005-valid-risk-action",
    ],
)
def test_valid_citations_pass(case_id):
    _, _, _, result = _result(case_id)

    assert result.status == "accepted"
    assert result.fallback_used is False
    assert "[evidence:" in result.rendered_text


@pytest.mark.parametrize(
    ("case_id", "reason"),
    [
        ("p3k-006-invalid-id", "invalid_evidence_ids"),
        ("p3k-009-amount-mismatch", "mismatched_evidence_claim"),
        ("p3k-010-vendor-mismatch", "mismatched_evidence_claim"),
        ("p3k-011-policy-approver", "unsupported_claims"),
        ("p3k-012-risk-mismatch", "risk_level_copy_mismatch"),
        ("p3k-013-action-mismatch", "recommended_action_copy_mismatch"),
        ("p3k-014-multi-citation-missing", "anomaly_citation_missing"),
        ("p3k-015-bullet-no-citation", "schema_invalid:ValidationError"),
        ("p3k-016-claim-type-mismatch", "mismatched_evidence_claim"),
        ("p3k-017-fill-missing-po", "mismatched_evidence_claim"),
        ("p3k-018-fill-missing-grn", "mismatched_evidence_claim"),
    ],
)
def test_invalid_citations_fail_closed(case_id, reason):
    case, _, _, result = _result(case_id)

    assert result.status == "rejected"
    assert result.fallback_used is True
    assert reason in result.validation.reject_reasons
    assert result.rendered_text == DeterministicTemplateRenderer().render(
        case.input_facts
    )
    assert "[evidence:" not in result.rendered_text


def test_renderer_only_accepts_validated_citation_and_matching_facts():
    first = _case("p3k-001-valid-po-amount")
    second = _case("p3k-002-valid-grn-missing")
    catalog, payload = materialize_citation_case(first)
    candidate = build_rule_only_citation_explanation(first.input_facts, catalog)
    validation, validated = ClaimEvidenceValidator().validate(
        first.input_facts, catalog, candidate
    )

    assert validation.passed is True
    with pytest.raises(TypeError, match="ValidatedCitationExplanation"):
        CitationRenderer().render(first.input_facts, catalog, payload)
    with pytest.raises(ValueError, match="facts 不匹配"):
        CitationRenderer().render(second.input_facts, catalog, validated)


def test_evidence_catalog_is_stable_and_only_uses_input_facts():
    case = _case("p3k-001-valid-po-amount")
    first, _ = materialize_citation_case(case)
    second, _ = materialize_citation_case(case)

    assert first == second
    assert first.facts_hash == case.input_facts.facts_hash()
    assert first.by_id()["po.total_amount"].value == "1000.00"
    assert first.by_id()["invoice.total_amount"].value == "1200.00"


def test_citation_evaluator_has_separate_metrics_and_debug_rows():
    report = evaluate_citation_challenge_set(load_citation_challenge_set(FIXTURE))
    required_metrics = {
        "evidence_id_precision",
        "evidence_id_recall",
        "claim_type_precision",
        "claim_type_recall",
        "unsupported_claim_rate",
        "invalid_evidence_id_rate",
        "mismatched_evidence_claim_rate",
        "missing_citation_rate",
    }
    required_row_fields = {
        "case_id",
        "expected_status",
        "actual_status",
        "failed_components",
        "invalid_evidence_ids",
        "mismatched_claims",
        "unsupported_claims",
        "missing_citations",
        "expected_evidence_ids",
        "actual_evidence_ids",
        "fallback_used",
        "rendered_text_preview",
    }

    assert report["baseline_passed"] is True
    assert report["citation_accept_reject_accuracy"] == 1.0
    assert report["fallback_accuracy"] == 1.0
    assert required_metrics <= set(report["accepted_only_metrics"])
    assert required_metrics <= set(report["all_candidate_metrics"])
    assert report["accepted_only_metrics"]["unsupported_claim_rate"] == 0.0
    assert report["all_candidate_metrics"]["missing_citation_rate"] > 0.0
    assert report["reject_reason_distribution"]
    assert required_row_fields <= set(report["per_case_debug_rows"][0])
