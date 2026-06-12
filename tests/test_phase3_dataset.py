"""Phase 3 synthetic 数据契约与可复现性测试。"""

from collections import Counter
import hashlib
import json
import re

from procureguard.phase3.dataset import ANOMALY_LABELS, ANSWER_SECTIONS, generate_samples
from procureguard.phase3.schemas import AnomalyType


def serialized(samples) -> bytes:
    """使用与生成脚本一致的稳定序列化方式。"""

    return "".join(
        json.dumps(sample.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for sample in samples
    ).encode("utf-8")


def test_dataset_is_reproducible_with_fixed_seed():
    first = generate_samples(seed=42)
    second = generate_samples(seed=42)
    other = generate_samples(seed=43)

    assert hashlib.sha256(serialized(first)).digest() == hashlib.sha256(serialized(second)).digest()
    assert serialized(first) != serialized(other)


def test_dataset_counts_and_fixed_splits():
    samples = generate_samples(seed=42)

    assert len(samples) == 200
    assert Counter(sample.split for sample in samples) == {
        "train": 160,
        "validation": 20,
        "test": 20,
    }
    assert Counter(sample.anomaly_type for sample in samples) == {
        anomaly_type: 25 for anomaly_type in AnomalyType
    }


def test_contract_keeps_deterministic_facts_and_generated_output_separate():
    samples = generate_samples(seed=42)
    combination = next(
        sample for sample in samples if sample.anomaly_type == AnomalyType.MULTI_ISSUE_COMBINATION
    )

    assert combination.risk_level == combination.input_facts.risk_level
    assert combination.recommended_action == combination.input_facts.recommended_action
    assert len(combination.input_facts.anomaly_types) >= 2
    assert combination.expected_explanation.startswith("异常类型：")
    assert "关键事实：" in combination.expected_explanation
    assert "审核结论：" in combination.expected_explanation
    assert all(sample.metadata["synthetic"] is True for sample in samples)


def test_gold_answers_use_fixed_fact_constrained_sections():
    samples = generate_samples(seed=42)

    assert all(
        all(section in sample.expected_explanation for section in ANSWER_SECTIONS)
        for sample in samples
    )
    assert all("事实边界：" in sample.expected_explanation for sample in samples)
    assert all("禁止补全：" in sample.expected_explanation for sample in samples)


def test_missing_goods_receipt_gold_never_invents_grn():
    sample = next(
        sample
        for sample in generate_samples(seed=42)
        if sample.anomaly_type == AnomalyType.MISSING_GOODS_RECEIPT
    )

    assert sample.input_facts.grn_number is None
    assert "收货单号：未提供" in sample.expected_explanation
    assert "缺失" in sample.expected_explanation
    assert "不得根据发票号推断收货单号" in sample.expected_explanation
    assert not re.search(r"\bGRN-\d+", sample.expected_explanation)


def test_quantity_mismatch_gold_does_not_add_amount_comparison():
    sample = next(
        sample
        for sample in generate_samples(seed=42)
        if sample.anomaly_type == AnomalyType.QUANTITY_MISMATCH
    )

    assert "发票数量" in sample.expected_explanation
    assert "收货数量" in sample.expected_explanation
    assert "没有金额不一致证据时不得生成金额对比" in sample.expected_explanation
    assert "订单金额" not in sample.expected_explanation
    assert "差额" not in sample.expected_explanation


def test_multi_issue_gold_only_mentions_input_anomaly_types():
    sample = next(
        sample
        for sample in generate_samples(seed=42)
        if sample.anomaly_type == AnomalyType.MULTI_ISSUE_COMBINATION
    )
    allowed = set(sample.input_facts.anomaly_types)

    for anomaly_type, label in ANOMALY_LABELS.items():
        if anomaly_type in allowed or anomaly_type == AnomalyType.MULTI_ISSUE_COMBINATION:
            continue
        assert label not in sample.expected_explanation


def test_generated_files_match_contract_and_summary():
    paths = {
        "train": "data/phase3/generated/train.jsonl",
        "validation": "data/phase3/generated/validation.jsonl",
        "test": "data/phase3/generated/test.jsonl",
    }
    counts = {}
    for split, path in paths.items():
        rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
        counts[split] = len(rows)
        assert all(row["split"] == split for row in rows)
        assert all(row["metadata"]["synthetic"] is True for row in rows)

    summary = json.load(open("reports/phase3/dataset_summary.json", encoding="utf-8"))
    assert counts == summary["split_counts"]
    assert summary["sample_count"] == 200
    assert summary["synthetic_only"] is True
