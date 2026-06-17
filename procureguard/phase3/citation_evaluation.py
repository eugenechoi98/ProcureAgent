"""Phase 3K citation challenge set、候选变异与 debug evaluator。"""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from procureguard.phase3.explanation.evidence_citation import (
    CitationExplanationResult,
    CitationExplanationService,
    CitationStructuredExplanation,
    EvidenceCatalog,
    build_evidence_catalog,
    build_rule_only_citation_explanation,
)
from procureguard.phase3.explanation.facts import CanonicalAuditFacts


class CitationChallengeCase(BaseModel):
    """单条 synthetic citation challenge。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    risk_category: str
    input_facts: CanonicalAuditFacts
    mutation: str = "none"
    expected_status: str
    expected_reject_reasons: list[str] = Field(default_factory=list)
    expected_evidence_ids: list[str]
    evidence_catalog_source: str = "derived_from_input_facts"
    candidate_source: str = "rule_only_then_mutation"
    synthetic_fixture: bool = True


class CitationChallengeSet(BaseModel):
    """Phase 3K 测试集，不是训练数据。"""

    model_config = ConfigDict(extra="forbid")

    challenge_set_id: str
    purpose: str
    training_data: bool
    cases: list[CitationChallengeCase] = Field(min_length=20, max_length=40)


def load_citation_challenge_set(path: Path) -> CitationChallengeSet:
    """读取 UTF-8 citation fixture。"""

    return CitationChallengeSet.model_validate_json(path.read_text(encoding="utf-8"))


def materialize_citation_case(
    case: CitationChallengeCase,
) -> tuple[EvidenceCatalog, dict[str, Any]]:
    """从 fixture 构造 catalog 和候选，并施加单一风险变异。"""

    catalog = build_evidence_catalog(case.input_facts)
    payload = build_rule_only_citation_explanation(
        case.input_facts, catalog
    ).model_dump(mode="json")
    mutation = case.mutation
    if mutation == "none":
        return catalog, payload
    if mutation == "invalid_evidence_id":
        payload["explanation_bullets"][0]["evidence_ids"] = ["po.unknown"]
        payload["cited_evidence_ids"][0] = "po.unknown"
    elif mutation == "amount_mismatch":
        payload["explanation_bullets"][0]["text"] += " 金额 USD 8100.24。"
    elif mutation == "vendor_mismatch":
        payload["explanation_bullets"][0]["text"] += " 供应商 Other Vendor。"
    elif mutation == "unsupported_approver":
        payload["explanation_bullets"][0]["text"] += " 审批人 CFO 已批准。"
    elif mutation == "action_mismatch":
        payload["recommended_action_copy"] = "auto_approve"
        bullet = next(item for item in payload["explanation_bullets"] if item["claim_type"] == "recommended_action")
        bullet["text"] = "建议动作是 auto_approve。"
    elif mutation == "risk_mismatch":
        payload["risk_level_copy"] = "high"
        bullet = next(item for item in payload["explanation_bullets"] if item["claim_type"] == "risk_level")
        bullet["text"] = "风险等级为 high。"
    elif mutation == "anomaly_citation_missing":
        bullet = next(item for item in payload["explanation_bullets"] if item["claim_type"] in ("anomaly", "duplicate_invoice"))
        bullet["evidence_ids"] = ["risk.level"]
        payload["cited_evidence_ids"] = list(dict.fromkeys(eid for item in payload["explanation_bullets"] for eid in item["evidence_ids"]))
    elif mutation == "bullet_without_citation":
        payload["explanation_bullets"][0]["evidence_ids"] = []
    elif mutation == "unrelated_evidence":
        payload["explanation_bullets"][0]["evidence_ids"] = ["action.recommended"]
        payload["cited_evidence_ids"] = list(dict.fromkeys(eid for item in payload["explanation_bullets"] for eid in item["evidence_ids"]))
    elif mutation == "claim_type_mismatch":
        payload["explanation_bullets"][0]["claim_type"] = "policy_rule"
    elif mutation == "fill_missing_po":
        payload["explanation_bullets"][0]["text"] += " 采购订单 PO-999999 已找到。"
    elif mutation == "fill_missing_grn":
        payload["explanation_bullets"][0]["text"] += " 收货单 GRN-999999 已找到。"
    elif mutation == "po_claims_grn":
        payload["explanation_bullets"][0]["claim_type"] = "grn_reference"
        payload["explanation_bullets"][0]["text"] = "收货单 GRN-999999 存在。"
        payload["explanation_bullets"][0]["evidence_ids"] = ["po.number"]
        payload["cited_evidence_ids"] = list(dict.fromkeys(eid for item in payload["explanation_bullets"] for eid in item["evidence_ids"]))
    elif mutation == "policy_adds_approver":
        bullet = next(item for item in payload["explanation_bullets"] if item["claim_type"] == "policy_rule")
        bullet["text"] += " 审批人 CFO 必须批准。"
    elif mutation == "multi_anomaly_citation_missing":
        anomaly_bullets = [item for item in payload["explanation_bullets"] if item["claim_type"] in ("anomaly", "duplicate_invoice")]
        anomaly_bullets[-1]["evidence_ids"] = ["risk.level"]
        payload["cited_evidence_ids"] = list(dict.fromkeys(eid for item in payload["explanation_bullets"] for eid in item["evidence_ids"]))
    elif mutation == "citation_union_mismatch":
        payload["cited_evidence_ids"] = []
    else:
        raise ValueError(f"未知 mutation: {mutation}")
    return catalog, payload


def evaluate_citation_challenge_set(challenge_set: CitationChallengeSet) -> dict[str, Any]:
    """输出 accepted-only、all-candidate 和逐案例 citation 指标。"""

    service = CitationExplanationService()
    rows: list[dict[str, Any]] = []
    records: list[tuple[CitationChallengeCase, CitationStructuredExplanation | None, CitationExplanationResult]] = []
    for case in challenge_set.cases:
        catalog, payload = materialize_citation_case(case)
        detected_missing_citations = [
            f"bullet_{index}"
            for index, bullet in enumerate(payload.get("explanation_bullets", []), start=1)
            if not bullet.get("evidence_ids")
        ]
        try:
            candidate = CitationStructuredExplanation.model_validate(payload)
        except Exception:
            candidate = None
        result = service.explain(case.input_facts, catalog, copy.deepcopy(payload))
        actual_ids = set(candidate.cited_evidence_ids) if candidate else set()
        expected_ids = set(case.expected_evidence_ids)
        expected_reasons_found = all(reason in result.validation.reject_reasons for reason in case.expected_reject_reasons)
        rows.append({
            "case_id": case.case_id,
            "expected_status": case.expected_status,
            "actual_status": result.status,
            "status_match": case.expected_status == result.status,
            "expected_reasons_found": expected_reasons_found,
            "failed_components": list(result.validation.reject_reasons),
            "invalid_evidence_ids": list(result.validation.invalid_evidence_ids),
            "mismatched_claims": list(result.validation.mismatched_claims),
            "unsupported_claims": list(result.validation.unsupported_claims),
            "missing_citations": list(
                dict.fromkeys(
                    [*result.validation.missing_citations, *detected_missing_citations]
                )
            ),
            "expected_evidence_ids": sorted(expected_ids),
            "actual_evidence_ids": sorted(actual_ids),
            "fallback_used": result.fallback_used,
            "rendered_text_preview": result.rendered_text[:180],
        })
        records.append((case, candidate, result))
    all_metrics = _metrics(records, accepted_only=False)
    accepted_metrics = _metrics(records, accepted_only=True)
    report = {
        "phase": "Phase 3K",
        "baseline": "rule_only_evidence_citation",
        "sample_count": len(challenge_set.cases),
        "training_performed": False,
        "model_loaded": False,
        "api_integration": False,
        "official_default": "deterministic_template",
        "official_default_changed": False,
        "citation_accept_reject_accuracy": sum(row["status_match"] for row in rows) / len(rows),
        "fallback_accuracy": sum(row["fallback_used"] == (row["actual_status"] == "rejected") for row in rows) / len(rows),
        "accepted_only_metrics": accepted_metrics,
        "all_candidate_metrics": all_metrics,
        "reject_reason_distribution": dict(sorted(Counter(reason for _, _, result in records for reason in result.validation.reject_reasons).items())),
        "per_case_debug_rows": rows,
    }
    report["baseline_passed"] = (
        report["citation_accept_reject_accuracy"] == 1.0
        and report["fallback_accuracy"] == 1.0
        and accepted_metrics["unsupported_claim_rate"] == 0.0
        and all(row["expected_reasons_found"] for row in rows)
    )
    return report


def _metrics(
    records: list[tuple[CitationChallengeCase, CitationStructuredExplanation | None, CitationExplanationResult]],
    accepted_only: bool,
) -> dict[str, float]:
    """分别计算 accepted-only 与所有候选指标。"""

    selected = [record for record in records if not accepted_only or record[2].status == "accepted"]
    evidence_tp = evidence_fp = evidence_fn = 0
    claim_tp = claim_fp = claim_fn = 0
    unsupported = invalid = mismatch = missing = 0
    for case, candidate, result in selected:
        expected_ids = set(case.expected_evidence_ids)
        actual_ids = set(candidate.cited_evidence_ids) if candidate else set()
        evidence_tp += len(actual_ids & expected_ids)
        evidence_fp += len(actual_ids - expected_ids)
        evidence_fn += len(expected_ids - actual_ids)
        expected = build_rule_only_citation_explanation(
            case.input_facts, build_evidence_catalog(case.input_facts)
        )
        expected_claims = {item.claim_type.value for item in expected.explanation_bullets}
        actual_claims = {item.claim_type.value for item in candidate.explanation_bullets} if candidate else set()
        claim_tp += len(actual_claims & expected_claims)
        claim_fp += len(actual_claims - expected_claims)
        claim_fn += len(expected_claims - actual_claims)
        unsupported += bool(result.validation.unsupported_claims)
        invalid += bool(result.validation.invalid_evidence_ids)
        mismatch += bool(result.validation.mismatched_claims)
        missing += bool(result.validation.missing_citations) or case.mutation == "bullet_without_citation"
    count = len(selected)
    return {
        "evidence_id_precision": _ratio(evidence_tp, evidence_tp + evidence_fp),
        "evidence_id_recall": _ratio(evidence_tp, evidence_tp + evidence_fn),
        "claim_type_precision": _ratio(claim_tp, claim_tp + claim_fp),
        "claim_type_recall": _ratio(claim_tp, claim_tp + claim_fn),
        "unsupported_claim_rate": _ratio(unsupported, count),
        "invalid_evidence_id_rate": _ratio(invalid, count),
        "mismatched_evidence_claim_rate": _ratio(mismatch, count),
        "missing_citation_rate": _ratio(missing, count),
    }


def _ratio(numerator: int, denominator: int) -> float:
    """空集合按完全正确处理。"""

    return numerator / denominator if denominator else 1.0
