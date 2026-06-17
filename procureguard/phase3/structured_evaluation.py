"""Phase 3J structured-output baseline 与逐案例 debug 评测。"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.structured_output import (
    StructuredExplanation,
    StructuredExplanationResult,
    StructuredExplanationService,
    build_rule_only_structured_explanation,
)


class StructuredChallengeCase(BaseModel):
    """独立 synthetic challenge fixture 单条案例。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    risk_category: str
    input_facts: CanonicalAuditFacts
    baseline: str = "rule_only"
    mutation: str = "none"
    expected_status: str
    expected_reject_reasons: list[str] = Field(default_factory=list)
    expected_output_source: str = "rule_only_from_input_facts"
    synthetic_fixture: bool = True


class StructuredChallengeSet(BaseModel):
    """Phase 3J challenge set，不作为训练数据。"""

    model_config = ConfigDict(extra="forbid")

    challenge_set_id: str
    purpose: str
    training_data: bool
    cases: list[StructuredChallengeCase] = Field(min_length=20, max_length=50)


def load_challenge_set(path: Path) -> StructuredChallengeSet:
    """读取固定 UTF-8 challenge fixture。"""

    return StructuredChallengeSet.model_validate_json(path.read_text(encoding="utf-8"))


def materialize_candidate(case: StructuredChallengeCase) -> Any:
    """从 rule-only 正确输出施加单一风险变异，便于定位拒绝原因。"""

    if case.baseline != "rule_only":
        raise ValueError(f"不支持 baseline: {case.baseline}")
    payload = build_rule_only_structured_explanation(case.input_facts).model_dump(
        mode="json"
    )
    mutation = case.mutation
    if mutation == "none":
        return payload
    if mutation == "schema_invalid":
        payload.pop("risk_level_copy")
    elif mutation == "unknown_po":
        payload["explanation_bullets"][0]["text"] += " 采购订单 PO-999999。"
    elif mutation == "unknown_grn":
        payload["explanation_bullets"][0]["text"] += " 收货单 GRN-999999。"
    elif mutation == "unknown_amount":
        payload["explanation_bullets"][0]["text"] += " 金额 USD 999999.00。"
    elif mutation == "unsupported_approver":
        payload["explanation_bullets"][0]["text"] += " 交由审批人处理。"
    elif mutation == "unknown_vendor":
        payload["explanation_bullets"][0]["text"] += " 供应商 Unknown Vendor LLC。"
    elif mutation == "action_mismatch":
        payload["recommended_action_copy"] = "auto_approve"
    elif mutation == "risk_mismatch":
        payload["risk_level_copy"] = "low" if case.input_facts.risk_level != "low" else "high"
    elif mutation == "anomaly_missing":
        payload["anomaly_types"] = payload["anomaly_types"][:-1]
    elif mutation == "anomaly_extra":
        payload["anomaly_types"].append("duplicate_invoice")
    elif mutation == "missing_field_omitted":
        payload["missing_fields"] = payload["missing_fields"][:-1]
    elif mutation == "missing_field_extra":
        payload["missing_fields"].append("vendor_name")
    elif mutation == "invalid_evidence_id":
        payload["explanation_bullets"][0]["evidence_ids"] = ["evidence.999"]
        payload["cited_evidence_ids"][0] = "evidence.999"
    elif mutation == "citation_union_mismatch":
        payload["cited_evidence_ids"] = []
    elif mutation == "evidence_claim_mismatch":
        payload["explanation_bullets"][0]["text"] = "金额存在明显差异。"
    elif mutation == "synonym_incomplete":
        payload["anomaly_types"] = payload["anomaly_types"][:-1]
        payload["explanation_bullets"][-1]["text"] = "还存在一项需要关注的问题。"
    else:
        raise ValueError(f"未知 mutation: {mutation}")
    return payload


def evaluate_structured_challenge_set(
    challenge_set: StructuredChallengeSet,
) -> dict[str, Any]:
    """运行离线 baseline 并输出汇总指标与逐案例 debug rows。"""

    service = StructuredExplanationService()
    rows: list[dict[str, Any]] = []
    parsed_candidates: list[StructuredExplanation | None] = []
    results: list[StructuredExplanationResult] = []
    for case in challenge_set.cases:
        payload = materialize_candidate(case)
        json_validity = _json_valid(payload)
        try:
            candidate = StructuredExplanation.model_validate(payload)
            schema_validity = True
        except (ValidationError, ValueError, TypeError):
            candidate = None
            schema_validity = False
        result = service.explain(case.input_facts, copy.deepcopy(payload))
        parsed_candidates.append(candidate)
        results.append(result)
        failed_components = list(result.validation.reject_reasons)
        expected_reasons_found = all(
            reason in failed_components for reason in case.expected_reject_reasons
        )
        rows.append(
            {
                "case_id": case.case_id,
                "risk_category": case.risk_category,
                "expected_status": case.expected_status,
                "actual_status": result.status,
                "status_match": case.expected_status == result.status,
                "expected_reasons_found": expected_reasons_found,
                "json_validity": json_validity,
                "schema_validity": schema_validity,
                "failed_components": failed_components,
                "unsupported_claims": list(result.validation.unsupported_claims),
                "invalid_evidence_ids": list(result.validation.invalid_evidence_ids),
                "action_mismatch": result.validation.action_mismatch,
                "risk_level_mismatch": result.validation.risk_level_mismatch,
                "anomaly_missing_or_extra": {
                    "missing": list(result.validation.anomaly_missing),
                    "extra": list(result.validation.anomaly_extra),
                },
                "rendered_text_preview": result.rendered_text[:180],
                "fallback_used": result.fallback_used,
            }
        )

    metrics = _aggregate_metrics(challenge_set.cases, parsed_candidates, results, rows)
    return {
        "phase": "Phase 3J",
        "baseline": "rule_only_structured_output",
        "challenge_set_id": challenge_set.challenge_set_id,
        "sample_count": len(challenge_set.cases),
        "training_performed": False,
        "api_integration": False,
        "live_inference": False,
        "official_default_changed": False,
        "official_default": "deterministic_template",
        "metric_scope": (
            "Field precision and recall include intentionally corrupted challenge "
            "candidates; pass/fail is based on expected status, expected reject "
            "reasons, fallback correctness, and zero unsupported accepted claims."
        ),
        "metrics": metrics,
        "reject_reason_distribution": dict(
            sorted(
                Counter(
                    reason
                    for result in results
                    for reason in result.validation.reject_reasons
                ).items()
            )
        ),
        "per_case_debug_rows": rows,
        "baseline_passed": all(
            row["status_match"] and row["expected_reasons_found"] for row in rows
        )
        and metrics["unsupported_claim_rate"] == 0.0,
    }


def _aggregate_metrics(
    cases: list[StructuredChallengeCase],
    candidates: list[StructuredExplanation | None],
    results: list[StructuredExplanationResult],
    rows: list[dict[str, Any]],
) -> dict[str, float]:
    """计算结构化输出要求的字段级指标。"""

    count = len(cases)
    parsed_count = sum(candidate is not None for candidate in candidates)
    anomaly_tp = anomaly_fp = anomaly_fn = 0
    missing_tp = missing_fp = missing_fn = 0
    evidence_tp = evidence_fp = evidence_fn = 0
    risk_matches = action_matches = 0
    accepted_with_unsupported = 0
    accepted_count = 0
    for case, candidate, result in zip(cases, candidates, results):
        if candidate is None:
            continue
        risk_matches += candidate.risk_level_copy == case.input_facts.risk_level
        action_matches += (
            candidate.recommended_action_copy == case.input_facts.recommended_action
        )
        anomaly_tp, anomaly_fp, anomaly_fn = _update_counts(
            {item.value for item in candidate.anomaly_types},
            {item.value for item in case.input_facts.anomaly_types},
            anomaly_tp,
            anomaly_fp,
            anomaly_fn,
        )
        missing_tp, missing_fp, missing_fn = _update_counts(
            set(candidate.missing_fields),
            set(case.input_facts.missing_fields),
            missing_tp,
            missing_fp,
            missing_fn,
        )
        actual_evidence = set(candidate.cited_evidence_ids)
        expected_evidence = set(
            build_rule_only_structured_explanation(case.input_facts).cited_evidence_ids
        )
        evidence_tp, evidence_fp, evidence_fn = _update_counts(
            actual_evidence,
            expected_evidence,
            evidence_tp,
            evidence_fp,
            evidence_fn,
        )
        if result.status == "accepted":
            accepted_count += 1
            accepted_with_unsupported += bool(result.validation.unsupported_claims)
    return {
        "json_validity": sum(row["json_validity"] for row in rows) / count,
        "schema_validity": sum(row["schema_validity"] for row in rows) / count,
        "risk_level_exact_match": _ratio(risk_matches, parsed_count),
        "recommended_action_exact_match": _ratio(action_matches, parsed_count),
        "anomaly_type_precision": _ratio(anomaly_tp, anomaly_tp + anomaly_fp),
        "anomaly_type_recall": _ratio(anomaly_tp, anomaly_tp + anomaly_fn),
        "missing_field_precision": _ratio(missing_tp, missing_tp + missing_fp),
        "missing_field_recall": _ratio(missing_tp, missing_tp + missing_fn),
        "evidence_id_precision": _ratio(evidence_tp, evidence_tp + evidence_fp),
        "evidence_id_recall": _ratio(evidence_tp, evidence_tp + evidence_fn),
        "unsupported_claim_rate": _ratio(accepted_with_unsupported, accepted_count),
        "expected_status_accuracy": sum(row["status_match"] for row in rows) / count,
        "fallback_accuracy": sum(
            row["fallback_used"] == (row["actual_status"] == "rejected")
            for row in rows
        )
        / count,
    }


def _update_counts(
    actual: set[str],
    expected: set[str],
    true_positive: int,
    false_positive: int,
    false_negative: int,
) -> tuple[int, int, int]:
    """更新 micro precision/recall 计数。"""

    return (
        true_positive + len(actual & expected),
        false_positive + len(actual - expected),
        false_negative + len(expected - actual),
    )


def _ratio(numerator: int, denominator: int) -> float:
    """空集合按完全正确处理。"""

    return numerator / denominator if denominator else 1.0


def _json_valid(payload: Any) -> bool:
    """确认 payload 可以稳定序列化为 JSON。"""

    try:
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True
