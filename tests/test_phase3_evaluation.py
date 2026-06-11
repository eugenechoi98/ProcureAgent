"""Phase 3 异常说明自动评测测试。"""

import pytest

from procureguard.phase3.dataset import generate_samples
from procureguard.phase3.evaluation import (
    aggregate_results,
    evaluate_explanation,
    evaluate_predictions,
)
from procureguard.phase3.schemas import AnomalyType


def sample_for(anomaly_type: AnomalyType):
    """取得指定异常类型的固定 fixture。"""

    return next(sample for sample in generate_samples(42) if sample.anomaly_type == anomaly_type)


def test_gold_explanation_passes_all_metrics():
    sample = sample_for(AnomalyType.AMOUNT_DISCREPANCY)

    result = evaluate_explanation(sample, sample.expected_explanation)

    assert result["format_compliance"] is True
    assert result["factual_consistency"] is True
    assert result["action_consistency"] is True
    assert result["anomaly_coverage"] == 1.0
    assert result["hallucination"] is False


def test_unknown_facts_and_changed_action_are_detected():
    sample = sample_for(AnomalyType.DUPLICATE_INVOICE)
    explanation = sample.expected_explanation.replace(
        sample.recommended_action, "auto_approve"
    ).replace(sample.input_facts.invoice_number, "INV-99999999")
    explanation += " 交由 CFO 根据政策第 9 条审批。"

    result = evaluate_explanation(sample, explanation)

    assert result["action_consistency"] is False
    assert result["factual_consistency"] is False
    assert result["hallucination"] is True
    assert any("unknown_identifier" in item for item in result["factual_violations"])
    assert any("CFO" in item for item in result["hallucination_violations"])


def test_unknown_quantity_vendor_and_conflicting_action_are_detected():
    sample = sample_for(AnomalyType.QUANTITY_MISMATCH)
    mismatch = next(item for item in sample.input_facts.mismatches if item["field"] == "quantity")
    explanation = sample.expected_explanation.replace(
        f"发票数量 {mismatch['invoice_value']}", "发票数量 999"
    )
    explanation = explanation.replace(sample.input_facts.vendor_name, "Unknown Vendor LLC")
    explanation += " 备选动作 auto_approve。"

    result = evaluate_explanation(sample, explanation)

    assert result["action_consistency"] is False
    assert result["factual_consistency"] is False
    assert result["hallucination"] is True
    assert any("unknown_quantity" in item for item in result["factual_violations"])
    assert any("unknown_vendor" in item for item in result["factual_violations"])


def test_multi_issue_coverage_penalizes_missing_anomaly():
    sample = sample_for(AnomalyType.MULTI_ISSUE_COMBINATION)
    missing_type = sample.input_facts.anomaly_types[-1]
    explanation = sample.expected_explanation.replace(missing_type.value, "")
    label_map = {
        AnomalyType.QUANTITY_MISMATCH: "收货数量不一致",
        AnomalyType.AMOUNT_DISCREPANCY: "发票金额不一致",
        AnomalyType.DUPLICATE_INVOICE: "重复发票",
        AnomalyType.MISSING_PO_NUMBER: "缺少采购订单号",
        AnomalyType.VENDOR_NAME_MISMATCH: "供应商名称不一致",
        AnomalyType.MISSING_GOODS_RECEIPT: "缺少收货记录",
        AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED: "高金额需要额外审批",
    }
    explanation = explanation.replace(label_map[missing_type], "未说明异常")

    result = evaluate_explanation(sample, explanation)

    assert result["anomaly_coverage"] < 1.0
    assert missing_type.value in result["missing_anomaly_types"]


def test_aggregate_uses_rates_and_missing_predictions_fail():
    samples = generate_samples(42)[:2]
    rows = [evaluate_explanation(sample, sample.expected_explanation) for sample in samples]

    metrics = aggregate_results(rows)

    assert metrics["sample_count"] == 2
    assert metrics["format_compliance"] == 1.0
    assert metrics["hallucination_rate"] == 0.0
    with pytest.raises(ValueError, match="缺少"):
        evaluate_predictions(samples, {samples[0].sample_id: samples[0].expected_explanation})
