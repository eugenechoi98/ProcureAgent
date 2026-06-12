"""确定性模板渲染器，作为 Phase 3H MVP 官方解释输出。"""

from __future__ import annotations

import json
from typing import Any

from procureguard.phase3.dataset import ANOMALY_LABELS
from procureguard.phase3.explanation.facts import CanonicalAuditFacts

TEMPLATE_VERSION = "phase3h-template-v1"
REQUIRED_TEMPLATE_SECTIONS = (
    "审核摘要：",
    "异常类型：",
    "关键证据：",
    "缺失字段：",
    "风险等级：",
    "建议动作：",
)


class DeterministicTemplateRenderer:
    """同一 Canonical Audit Facts 必须渲染出同一解释文本。"""

    version = TEMPLATE_VERSION

    def render(self, facts: CanonicalAuditFacts) -> str:
        """生成固定章节的采购审核说明。"""

        anomalies = "、".join(ANOMALY_LABELS[item] for item in facts.anomaly_types)
        evidence = self._render_evidence(facts)
        missing = self._render_missing_fields(facts)
        summary = (
            f"发现 {len(facts.anomaly_types)} 类异常，"
            f"风险等级为 {facts.risk_level}，建议动作 {facts.recommended_action}。"
        )
        return "\n".join(
            [
                f"审核摘要：{summary}",
                f"异常类型：{anomalies}",
                f"关键证据：{evidence}",
                f"缺失字段：{missing}",
                f"风险等级：{facts.risk_level}",
                f"建议动作：{facts.recommended_action}",
            ]
        )

    def _render_evidence(self, facts: CanonicalAuditFacts) -> str:
        """把事实字段和 evidence 转成稳定短句。"""

        parts = [
            f"供应商 {self._display(facts.vendor_name)}",
            f"发票号 {self._display(facts.invoice_number)}",
            f"采购订单号 {self._display(facts.po_number)}",
            f"收货单号 {self._display(facts.grn_number)}",
        ]
        if facts.total_amount is not None and facts.currency:
            parts.append(f"发票金额 {facts.currency} {facts.total_amount:.2f}")
        elif facts.total_amount is not None:
            parts.append(f"发票金额 {facts.total_amount:.2f}")
        for item in facts.evidence:
            parts.append(self._render_evidence_item(item))
        if facts.policy_flags:
            parts.append("政策标记 " + "、".join(facts.policy_flags))
        return "；".join(parts)

    def _render_missing_fields(self, facts: CanonicalAuditFacts) -> str:
        """缺失字段统一明确写未提供。"""

        if not facts.missing_fields:
            return "无"
        return "；".join(f"{field}：未提供（缺失）" for field in facts.missing_fields)

    def _render_evidence_item(self, item: dict[str, Any]) -> str:
        """对常见 evidence 做可读展示，未知结构保持 JSON 稳定输出。"""

        field = item.get("field")
        if field == "quantity":
            return (
                f"{item.get('item', '项目')} 发票数量 {item.get('invoice_value')}、"
                f"收货数量 {item.get('received_value')}"
            )
        if field == "total_amount":
            return (
                f"金额对比 发票 {item.get('invoice_value')}、"
                f"订单 {item.get('expected_value')}、差额 {item.get('diff')}"
            )
        if field == "vendor_name":
            return (
                f"供应商对比 发票 {item.get('invoice_value')}、"
                f"订单 {item.get('expected_value')}"
            )
        if field == "duplicate_invoice":
            return f"重复发票检查命中 {item.get('invoice_value')}"
        if field:
            return json.dumps(item, ensure_ascii=False, sort_keys=True)
        return json.dumps(item, ensure_ascii=False, sort_keys=True)

    def _display(self, value: object | None) -> str:
        """空值只显示未提供，不做推断。"""

        return str(value) if value not in (None, "") else "未提供（缺失）"
