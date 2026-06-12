"""生成可复现的 Phase 3 synthetic 异常说明数据。"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from procureguard.phase3.schemas import AnomalySample, AnomalyType, InputFacts

DEFAULT_SEED = 42
SAMPLES_PER_TYPE = 25
SPLITS = ("train", "validation", "test")
SINGLE_TYPES = [item for item in AnomalyType if item != AnomalyType.MULTI_ISSUE_COMBINATION]

ANOMALY_LABELS = {
    AnomalyType.QUANTITY_MISMATCH: "收货数量不一致",
    AnomalyType.AMOUNT_DISCREPANCY: "发票金额不一致",
    AnomalyType.DUPLICATE_INVOICE: "重复发票",
    AnomalyType.MISSING_PO_NUMBER: "缺少采购订单号",
    AnomalyType.VENDOR_NAME_MISMATCH: "供应商名称不一致",
    AnomalyType.MISSING_GOODS_RECEIPT: "缺少收货记录",
    AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED: "高金额需要额外审批",
    AnomalyType.MULTI_ISSUE_COMBINATION: "多异常组合",
}

VENDORS = [
    "Northwind Office Supplies",
    "Contoso Industrial Parts",
    "Fabrikam Logistics",
    "Adventure Works Services",
    "Alpine Technology Group",
    "Blue Yonder Components",
]
CURRENCIES = ["USD", "EUR", "GBP", "CNY"]
ITEMS = ["printer toner", "safety gloves", "network switch", "packing tape"]
ANSWER_SECTIONS = (
    "异常类型：",
    "事实边界：",
    "关键事实：",
    "缺失字段：",
    "禁止补全：",
    "审核结论：",
)


def _split_for(type_index: int, sample_index: int) -> str:
    """按异常类型稳定分层，并将 validation/test 总数都固定为 20。"""

    if sample_index < 20:
        return "train"
    validation_count = 3 if type_index < 4 else 2
    return "validation" if sample_index < 20 + validation_count else "test"


def _base_facts(rng: random.Random, serial: int) -> dict[str, Any]:
    amount = round(rng.uniform(450.0, 9800.0), 2)
    return {
        "vendor_name": rng.choice(VENDORS),
        "invoice_number": f"INV-{20260000 + serial:08d}",
        "po_number": f"PO-{710000 + serial:06d}",
        "grn_number": f"GRN-{810000 + serial:06d}",
        "total_amount": amount,
        "currency": rng.choice(CURRENCIES),
        "risk_level": "medium",
        "recommended_action": "request_human_approval",
        "policy_flags": [],
        "duplicate_check": True,
        "po_match": True,
        "grn_match": True,
        "amount_match": True,
        "mismatches": [],
        "evidence": [],
    }


def _apply_anomaly(
    facts: dict[str, Any], anomaly_type: AnomalyType, rng: random.Random
) -> None:
    """只把异常事实写入输入，不让解释文本承担规则计算。"""

    if anomaly_type == AnomalyType.QUANTITY_MISMATCH:
        invoiced = rng.randint(8, 30)
        received = rng.randint(1, invoiced - 1)
        item = rng.choice(ITEMS)
        facts["grn_match"] = False
        facts["mismatches"].append(
            {"field": "quantity", "item": item, "invoice_value": invoiced, "received_value": received}
        )
        facts["evidence"].append(
            {"field": "quantity", "item": item, "invoice_value": invoiced, "received_value": received}
        )
    elif anomaly_type == AnomalyType.AMOUNT_DISCREPANCY:
        expected = round(facts["total_amount"] * rng.uniform(0.72, 0.94), 2)
        facts["amount_match"] = False
        facts["po_match"] = False
        facts["mismatches"].append(
            {
                "field": "total_amount",
                "invoice_value": facts["total_amount"],
                "expected_value": expected,
                "diff": round(facts["total_amount"] - expected, 2),
            }
        )
    elif anomaly_type == AnomalyType.DUPLICATE_INVOICE:
        facts["duplicate_check"] = False
        facts["risk_level"] = "high"
        facts["recommended_action"] = "reject"
        facts["evidence"].append(
            {"field": "duplicate_invoice", "invoice_value": facts["invoice_number"], "received_value": "existing_record"}
        )
    elif anomaly_type == AnomalyType.MISSING_PO_NUMBER:
        facts["po_number"] = None
        facts["po_match"] = False
        facts["mismatches"].append(
            {"field": "po_number", "invoice_value": None, "expected_value": "required"}
        )
    elif anomaly_type == AnomalyType.VENDOR_NAME_MISMATCH:
        expected_vendor = rng.choice([item for item in VENDORS if item != facts["vendor_name"]])
        facts["po_match"] = False
        facts["mismatches"].append(
            {"field": "vendor_name", "invoice_value": facts["vendor_name"], "expected_value": expected_vendor}
        )
    elif anomaly_type == AnomalyType.MISSING_GOODS_RECEIPT:
        facts["grn_number"] = None
        facts["grn_match"] = False
        facts["mismatches"].append(
            {"field": "grn_number", "invoice_value": None, "expected_value": "required"}
        )
    elif anomaly_type == AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED:
        facts["total_amount"] = round(rng.uniform(10000.01, 85000.0), 2)
        facts["policy_flags"].append("high_value_approval_required")


def _display_value(value: str | None) -> str:
    """缺失字段统一写成未提供，不让模型学习补全。"""

    return value if value else "未提供（缺失）"


def _fact_phrases(facts: InputFacts) -> list[str]:
    """只列 input_facts 中存在或显式缺失的事实。"""

    phrases = [
        f"供应商 {facts.vendor_name}",
        f"发票号 {facts.invoice_number}",
        f"采购订单号 {_display_value(facts.po_number)}",
        f"收货单号 {_display_value(facts.grn_number)}",
        f"金额 {facts.currency} {facts.total_amount:.2f}",
    ]
    for mismatch in facts.mismatches:
        if mismatch["field"] == "quantity":
            phrases.append(
                f"{mismatch['item']} 发票数量 {mismatch['invoice_value']}、收货数量 {mismatch['received_value']}"
            )
        elif mismatch["field"] == "total_amount":
            phrases.append(
                f"订单金额 {facts.currency} {mismatch['expected_value']:.2f}、差额 {facts.currency} {mismatch['diff']:.2f}"
            )
        elif mismatch["field"] == "vendor_name":
            phrases.append(f"订单供应商 {mismatch['expected_value']}")
        elif mismatch["field"] == "po_number":
            phrases.append("采购订单号缺失，采购订单号：未提供")
        elif mismatch["field"] == "grn_number":
            phrases.append("收货记录缺失，收货单号：未提供")
    if not facts.duplicate_check:
        phrases.append("重复检查未通过")
    if facts.policy_flags:
        phrases.append("政策标记 " + "、".join(facts.policy_flags))
    return phrases


def _missing_field_phrases(facts: InputFacts) -> list[str]:
    """列出缺失字段，缺失必须用未提供或缺失表达。"""

    phrases: list[str] = []
    if facts.po_number is None:
        phrases.append("采购订单号：未提供（缺失）")
    if facts.grn_number is None:
        phrases.append("收货单号：未提供（缺失）")
    return phrases or ["无"]


def _forbidden_completion_phrases(facts: InputFacts) -> list[str]:
    """告诉模型哪些字段不能推断或补全。"""

    forbidden = ["不得补全未提供的 PO、GRN、发票号、金额、供应商或异常类型"]
    if facts.po_number is None:
        forbidden.append("不得根据发票号推断采购订单号")
    if facts.grn_number is None:
        forbidden.append("不得根据发票号推断收货单号")
    if all(item.get("field") != "total_amount" for item in facts.mismatches):
        forbidden.append("没有金额不一致证据时不得生成金额对比")
    if all(item.get("field") != "vendor_name" for item in facts.mismatches):
        forbidden.append("没有供应商不一致证据时不得生成供应商不匹配")
    return forbidden


def build_explanation(facts: InputFacts) -> str:
    """使用固定章节生成事实约束型 gold answer。"""

    labels = "、".join(ANOMALY_LABELS[item] for item in facts.anomaly_types)
    return (
        f"异常类型：{labels}\n"
        "事实边界：只引用 input_facts、mismatches、evidence 中给出的事实；"
        "缺失字段必须写未提供或缺失；不得推断未知单号、金额、供应商或异常类型。\n"
        f"关键事实：{'；'.join(_fact_phrases(facts))}。\n"
        f"缺失字段：{'；'.join(_missing_field_phrases(facts))}。\n"
        f"禁止补全：{'；'.join(_forbidden_completion_phrases(facts))}。\n"
        f"审核结论：风险等级 {facts.risk_level}；建议动作 {facts.recommended_action}。"
    )


def generate_samples(seed: int = DEFAULT_SEED) -> list[AnomalySample]:
    """生成 200 条固定分布的 synthetic 样本。"""

    rng = random.Random(seed)
    samples: list[AnomalySample] = []
    serial = 0
    for type_index, primary_type in enumerate(AnomalyType):
        for sample_index in range(SAMPLES_PER_TYPE):
            serial += 1
            facts_data = _base_facts(rng, serial)
            included = (
                rng.sample(SINGLE_TYPES, k=2 + (sample_index % 2))
                if primary_type == AnomalyType.MULTI_ISSUE_COMBINATION
                else [primary_type]
            )
            for included_type in included:
                _apply_anomaly(facts_data, included_type, rng)
            if any(item == AnomalyType.DUPLICATE_INVOICE for item in included):
                facts_data["risk_level"] = "high"
                facts_data["recommended_action"] = "reject"
            facts_data["anomaly_types"] = included
            facts = InputFacts.model_validate(facts_data)
            split = _split_for(type_index, sample_index)
            samples.append(
                AnomalySample(
                    sample_id=f"phase3-{primary_type.value}-{sample_index + 1:03d}",
                    anomaly_type=primary_type,
                    input_facts=facts,
                    expected_explanation=build_explanation(facts),
                    risk_level=facts.risk_level,
                    recommended_action=facts.recommended_action,
                    split=split,
                    metadata={
                        "synthetic": True,
                        "generator": "scripts/phase3/generate_anomaly_explanations.py",
                        "seed": seed,
                        "included_anomaly_types": [item.value for item in included],
                    },
                )
            )
    return samples


def _write_jsonl(path: Path, samples: list[AnomalySample]) -> str:
    content = "".join(
        json.dumps(sample.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for sample in samples
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def dataset_summary(samples: list[AnomalySample], hashes: dict[str, str]) -> dict[str, Any]:
    """汇总拆分、异常类型和可复现性信息。"""

    by_split = Counter(sample.split for sample in samples)
    by_type = Counter(sample.anomaly_type.value for sample in samples)
    by_split_type: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        by_split_type[split] = dict(
            sorted(Counter(
                sample.anomaly_type.value for sample in samples if sample.split == split
            ).items())
        )
    return {
        "dataset_name": "procureguard_phase3_synthetic_anomaly_explanations",
        "synthetic_only": True,
        "seed": samples[0].metadata["seed"] if samples else DEFAULT_SEED,
        "sample_count": len(samples),
        "split_counts": dict(sorted(by_split.items())),
        "anomaly_type_counts": dict(sorted(by_type.items())),
        "split_anomaly_type_counts": by_split_type,
        "gold_answer_contract": {
            "sections": list(ANSWER_SECTIONS),
            "missing_fields": "缺失字段必须写未提供或缺失，不得补全 PO、GRN、金额、发票号或供应商。",
            "multi_issue": "只覆盖 input_facts.anomaly_types 中列出的异常。",
            "generation_variable": "fact_constrained_prompt_and_uniform_expected_explanation_format",
        },
        "sha256": hashes,
    }


def summary_to_markdown(summary: dict[str, Any]) -> str:
    """生成人可读的数据集统计。"""

    lines = [
        "# Phase 3 Dataset Summary",
        "",
        f"- synthetic_only: {str(summary['synthetic_only']).lower()}",
        f"- seed: {summary['seed']}",
        f"- sample_count: {summary['sample_count']}",
        "",
        "## Split Counts",
        "",
        "| split | count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in summary["split_counts"].items())
    lines.extend(["", "## Anomaly Type Counts", "", "| anomaly_type | count |", "| --- | ---: |"])
    lines.extend(
        f"| {name} | {count} |" for name, count in summary["anomaly_type_counts"].items()
    )
    lines.extend(["", "## File Hashes", ""])
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in summary["sha256"].items())
    lines.extend(
        [
            "",
            "## Gold Answer Contract",
            "",
            "- 固定章节：`异常类型`、`事实边界`、`关键事实`、`缺失字段`、`禁止补全`、`审核结论`。",
            "- 缺失字段必须写 `未提供` 或 `缺失`。",
            "- 不得补全 PO、GRN、发票号、金额、供应商或未输入异常类型。",
            "- 多异常组合只覆盖 `input_facts.anomaly_types` 中存在的异常。",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def write_dataset(project_root: Path, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """写入固定数据拆分和两种统计报告。"""

    samples = generate_samples(seed)
    generated_dir = project_root / "data" / "phase3" / "generated"
    hashes = {
        f"{split}.jsonl": _write_jsonl(
            generated_dir / f"{split}.jsonl",
            [sample for sample in samples if sample.split == split],
        )
        for split in SPLITS
    }
    summary = dataset_summary(samples, hashes)
    report_dir = project_root / "reports" / "phase3"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (report_dir / "dataset_summary.md").write_text(
        summary_to_markdown(summary), encoding="utf-8", newline="\n"
    )
    return summary
