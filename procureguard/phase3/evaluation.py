"""Phase 3 异常说明的自动评测规则。"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Iterable

from procureguard.phase3.dataset import ANOMALY_LABELS
from procureguard.phase3.schemas import AnomalySample, AnomalyType

REQUIRED_SECTIONS = ("异常类型：", "关键事实：", "审核结论：")
IDENTIFIER_PATTERN = re.compile(r"\b(?:INV|PO|GRN)-[A-Z0-9-]+\b", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"\b(?:USD|EUR|GBP|CNY)\b")
MONEY_PATTERN = re.compile(r"\b(?:USD|EUR|GBP|CNY)\s+([0-9][0-9,]*\.\d{2})\b")
QUANTITY_PATTERN = re.compile(r"(?:发票数量|收货数量)\s*(\d+(?:\.\d+)?)")
VENDOR_PATTERN = re.compile(r"(?:供应商|订单供应商)\s+([^；。\n]+)")
ACTIONS = ("auto_approve", "request_human_approval", "reject")
FORBIDDEN_POLICY_TERMS = (
    "CFO",
    "CEO",
    "首席财务官",
    "部门经理",
    "政策第",
    "条款第",
    "审批人",
)


def load_samples(path: Path) -> list[AnomalySample]:
    """从 JSONL 加载并校验 Phase 3 样本。"""

    samples: list[AnomalySample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    samples.append(AnomalySample.model_validate_json(line))
                except Exception as exc:
                    raise ValueError(f"{path}:{line_number} 样本无效: {exc}") from exc
    return samples


def load_predictions(path: Path) -> dict[str, str]:
    """读取包含 sample_id 和 explanation 的推理结果。"""

    predictions: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row.get("sample_id"), str) or not isinstance(
                row.get("explanation"), str
            ):
                raise ValueError(f"{path}:{line_number} 必须包含字符串 sample_id/explanation")
            predictions[row["sample_id"]] = row["explanation"]
    return predictions


def _known_identifiers(sample: AnomalySample) -> set[str]:
    facts = sample.input_facts
    return {
        value.upper()
        for value in (facts.invoice_number, facts.po_number, facts.grn_number)
        if value
    }


def _known_amounts(sample: AnomalySample) -> set[str]:
    amounts = {f"{sample.input_facts.total_amount:.2f}"}
    for item in sample.input_facts.mismatches + sample.input_facts.evidence:
        for key in ("invoice_value", "expected_value", "received_value", "diff"):
            value = item.get(key)
            if isinstance(value, float):
                amounts.add(f"{value:.2f}")
    return amounts


def _known_quantities(sample: AnomalySample) -> set[str]:
    quantities: set[str] = set()
    for item in sample.input_facts.mismatches + sample.input_facts.evidence:
        if item.get("field") != "quantity":
            continue
        for key in ("invoice_value", "expected_value", "received_value"):
            value = item.get(key)
            if isinstance(value, (int, float)):
                quantities.add(str(value))
    return quantities


def _known_vendors(sample: AnomalySample) -> set[str]:
    vendors = {sample.input_facts.vendor_name}
    for item in sample.input_facts.mismatches + sample.input_facts.evidence:
        if item.get("field") == "vendor_name":
            vendors.update(
                str(value)
                for value in (item.get("invoice_value"), item.get("expected_value"))
                if value
            )
    return vendors


def critical_fact_tokens(sample: AnomalySample) -> list[str]:
    """返回每类异常必须在说明中出现的关键事实。"""

    facts = sample.input_facts
    tokens = [facts.invoice_number]
    for anomaly_type in facts.anomaly_types:
        if anomaly_type == AnomalyType.QUANTITY_MISMATCH:
            mismatch = next(item for item in facts.mismatches if item["field"] == "quantity")
            tokens.extend(
                [str(mismatch["item"]), str(mismatch["invoice_value"]), str(mismatch["received_value"])]
            )
        elif anomaly_type == AnomalyType.AMOUNT_DISCREPANCY:
            mismatch = next(item for item in facts.mismatches if item["field"] == "total_amount")
            tokens.extend(
                [facts.currency, f"{facts.total_amount:.2f}", f"{mismatch['expected_value']:.2f}"]
            )
        elif anomaly_type == AnomalyType.DUPLICATE_INVOICE:
            tokens.extend([facts.vendor_name, "重复检查未通过"])
        elif anomaly_type == AnomalyType.MISSING_PO_NUMBER:
            tokens.append("采购订单号缺失")
        elif anomaly_type == AnomalyType.VENDOR_NAME_MISMATCH:
            mismatch = next(item for item in facts.mismatches if item["field"] == "vendor_name")
            tokens.extend([facts.vendor_name, str(mismatch["expected_value"])])
        elif anomaly_type == AnomalyType.MISSING_GOODS_RECEIPT:
            tokens.append("收货记录缺失")
        elif anomaly_type == AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED:
            tokens.extend([facts.currency, f"{facts.total_amount:.2f}", "high_value_approval_required"])
    return list(dict.fromkeys(tokens))


def factual_violations(sample: AnomalySample, explanation: str) -> list[str]:
    """检测输出里不属于输入事实的单号、币种和金额。"""

    violations: list[str] = []
    known_ids = _known_identifiers(sample)
    for identifier in IDENTIFIER_PATTERN.findall(explanation):
        if identifier.upper() not in known_ids:
            violations.append(f"unknown_identifier:{identifier}")

    known_currencies = {sample.input_facts.currency}
    for currency in CURRENCY_PATTERN.findall(explanation):
        if currency not in known_currencies:
            violations.append(f"unknown_currency:{currency}")

    known_amounts = _known_amounts(sample)
    for amount in MONEY_PATTERN.findall(explanation):
        normalized = amount.replace(",", "")
        if normalized not in known_amounts:
            violations.append(f"unknown_amount:{amount}")

    known_quantities = _known_quantities(sample)
    for quantity in QUANTITY_PATTERN.findall(explanation):
        if quantity not in known_quantities:
            violations.append(f"unknown_quantity:{quantity}")

    known_vendors = _known_vendors(sample)
    for vendor in VENDOR_PATTERN.findall(explanation):
        if vendor.strip() not in known_vendors:
            violations.append(f"unknown_vendor:{vendor.strip()}")
    return violations


def hallucination_violations(sample: AnomalySample, explanation: str) -> list[str]:
    """检测不存在的政策、审批角色和业务事实。"""

    violations = factual_violations(sample, explanation)
    allowed_text = json.dumps(sample.input_facts.model_dump(mode="json"), ensure_ascii=False)
    for term in FORBIDDEN_POLICY_TERMS:
        if term in explanation and term not in allowed_text:
            violations.append(f"unsupported_policy_or_approver:{term}")
    return violations


def evaluate_explanation(sample: AnomalySample, explanation: str) -> dict[str, Any]:
    """按统一 rubric 评测一条模型输出。"""

    present_sections = [section for section in REQUIRED_SECTIONS if section in explanation]
    anomaly_hits = [
        anomaly_type.value in explanation or ANOMALY_LABELS[anomaly_type] in explanation
        for anomaly_type in sample.input_facts.anomaly_types
    ]
    fact_tokens = critical_fact_tokens(sample)
    fact_hits = [token in explanation for token in fact_tokens]
    mentioned_actions = {action for action in ACTIONS if action in explanation}
    action_ok = mentioned_actions == {sample.recommended_action}
    risk_ok = sample.risk_level in explanation
    factual_errors = factual_violations(sample, explanation)
    hallucinations = hallucination_violations(sample, explanation)

    format_components = {
        "required_sections": len(present_sections) == len(REQUIRED_SECTIONS),
        "anomaly_type_present": all(anomaly_hits),
        "critical_facts_present": all(fact_hits),
        "recommended_action_present": action_ok,
        "risk_level_present": risk_ok,
    }
    return {
        "sample_id": sample.sample_id,
        "format_compliance": all(format_components.values()),
        "format_components": format_components,
        "factual_consistency": not factual_errors,
        "factual_violations": factual_errors,
        "action_consistency": action_ok,
        "anomaly_coverage": sum(anomaly_hits) / len(anomaly_hits),
        "missing_anomaly_types": [
            item.value for item, hit in zip(sample.input_facts.anomaly_types, anomaly_hits) if not hit
        ],
        "hallucination": bool(hallucinations),
        "hallucination_violations": hallucinations,
        "missing_critical_facts": [token for token, hit in zip(fact_tokens, fact_hits) if not hit],
    }


def aggregate_results(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """汇总为 base 与 fine-tuned 可直接比较的比例指标。"""

    rows = list(results)
    if not rows:
        raise ValueError("没有可汇总的评测结果")
    count = len(rows)
    return {
        "sample_count": count,
        "format_compliance": sum(row["format_compliance"] for row in rows) / count,
        "factual_consistency": sum(row["factual_consistency"] for row in rows) / count,
        "action_consistency": sum(row["action_consistency"] for row in rows) / count,
        "anomaly_coverage": sum(row["anomaly_coverage"] for row in rows) / count,
        "hallucination_rate": sum(row["hallucination"] for row in rows) / count,
        "failure_counts": dict(
            Counter(
                key
                for row in rows
                for key, failed in (
                    ("format_compliance", not row["format_compliance"]),
                    ("factual_consistency", not row["factual_consistency"]),
                    ("action_consistency", not row["action_consistency"]),
                    ("hallucination", row["hallucination"]),
                )
                if failed
            )
        ),
    }


def evaluate_predictions(
    samples: list[AnomalySample], predictions: dict[str, str]
) -> dict[str, Any]:
    """要求每条测试样本都有预测，避免静默漏评。"""

    missing = [sample.sample_id for sample in samples if sample.sample_id not in predictions]
    if missing:
        raise ValueError(f"缺少 {len(missing)} 条预测，示例: {missing[:3]}")
    rows = [evaluate_explanation(sample, predictions[sample.sample_id]) for sample in samples]
    return {"metrics": aggregate_results(rows), "samples": rows}


def comparison_to_markdown(reports: dict[str, dict[str, Any]]) -> str:
    """将 base/fine-tuned 结果导出为同口径表格。"""

    lines = [
        "# Phase 3 Explanation Evaluation",
        "",
        "| model | samples | format | factual | action | anomaly coverage | hallucination rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, report in reports.items():
        metrics = report["metrics"]
        lines.append(
            f"| {name} | {metrics['sample_count']} | {metrics['format_compliance']:.4f} | "
            f"{metrics['factual_consistency']:.4f} | {metrics['action_consistency']:.4f} | "
            f"{metrics['anomaly_coverage']:.4f} | {metrics['hallucination_rate']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)
