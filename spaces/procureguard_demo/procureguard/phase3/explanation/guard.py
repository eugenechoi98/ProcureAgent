"""LoRA 输出 guard，拒绝新增事实或改写审核结论。"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from procureguard.phase3.dataset import ANOMALY_LABELS
from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.renderer import REQUIRED_TEMPLATE_SECTIONS

IDENTIFIER_PATTERN = re.compile(r"\b(?:INV|PO|GRN)-[A-Z0-9-]+\b", re.IGNORECASE)
MONEY_PATTERN = re.compile(r"\b(?:USD|EUR|GBP|CNY)\s+([0-9][0-9,]*\.\d{2})\b")
VENDOR_PATTERN = re.compile(r"(?:供应商|订单供应商)\s+([^；。\n]+)")
RISK_LEVELS = ("low", "medium", "high")
ACTIONS = ("auto_approve", "request_human_approval", "reject")
RISK_FIELD_PATTERN = re.compile(r"风险等级[：:]\s*(low|medium|high)")
ACTION_FIELD_PATTERN = re.compile(
    r"建议动作[：:]\s*(auto_approve|request_human_approval|reject)"
)
FORBIDDEN_POLICY_TERMS = (
    "CFO",
    "CEO",
    "首席财务官",
    "部门经理",
    "政策第",
    "条款第",
    "审批人",
)


class GuardResult(BaseModel):
    """guard 的可审计结果。"""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    violations: list[str] = Field(default_factory=list)


class LoRAOutputGuard:
    """检查模型输出是否仍被 Canonical Audit Facts 约束。"""

    def verify(self, facts: CanonicalAuditFacts, output: str) -> GuardResult:
        """返回是否可使用，以及具体拒绝原因。"""

        violations: list[str] = []
        if not output.strip():
            return GuardResult(passed=False, violations=["empty_output"])
        violations.extend(self._missing_sections(output))
        violations.extend(self._unknown_identifiers(facts, output))
        violations.extend(self._unknown_amounts(facts, output))
        violations.extend(self._unknown_vendors(facts, output))
        violations.extend(self._unsupported_policy_terms(facts, output))
        violations.extend(self._decision_changes(facts, output))
        violations.extend(self._anomaly_changes(facts, output))
        return GuardResult(passed=not violations, violations=violations)

    def _missing_sections(self, output: str) -> list[str]:
        """固定章节缺失时直接拒绝。"""

        return [
            f"missing_section:{section}"
            for section in REQUIRED_TEMPLATE_SECTIONS
            if section not in output
        ]

    def _unknown_identifiers(
        self, facts: CanonicalAuditFacts, output: str
    ) -> list[str]:
        """未知 PO/GRN/发票号不得出现。"""

        known = facts.known_identifiers()
        return [
            f"unknown_identifier:{identifier}"
            for identifier in IDENTIFIER_PATTERN.findall(output)
            if identifier.upper() not in known
        ]

    def _unknown_amounts(self, facts: CanonicalAuditFacts, output: str) -> list[str]:
        """未知金额不得出现。"""

        known = facts.known_amounts()
        violations: list[str] = []
        for amount in MONEY_PATTERN.findall(output):
            normalized = amount.replace(",", "")
            if normalized not in known:
                violations.append(f"unknown_amount:{amount}")
        return violations

    def _unknown_vendors(self, facts: CanonicalAuditFacts, output: str) -> list[str]:
        """未知供应商不得出现。"""

        known = facts.known_vendors()
        if not known:
            return []
        violations: list[str] = []
        for vendor in VENDOR_PATTERN.findall(output):
            value = vendor.strip()
            if value and value not in known and not value.startswith("未提供"):
                violations.append(f"unknown_vendor:{value}")
        return violations

    def _unsupported_policy_terms(
        self, facts: CanonicalAuditFacts, output: str
    ) -> list[str]:
        """不在事实中的政策和审批角色不得出现。"""

        allowed_text = facts.model_dump_json(exclude_none=False)
        return [
            f"unsupported_policy_or_approver:{term}"
            for term in FORBIDDEN_POLICY_TERMS
            if term in output and term not in allowed_text
        ]

    def _decision_changes(self, facts: CanonicalAuditFacts, output: str) -> list[str]:
        """风险等级和建议动作只能等于事实值。"""

        violations: list[str] = []
        mentioned_risks = set(RISK_FIELD_PATTERN.findall(output))
        if mentioned_risks != {facts.risk_level}:
            violations.append(
                "changed_risk_level:"
                + ",".join(sorted(mentioned_risks or {"missing"}))
            )
        mentioned_actions = set(ACTION_FIELD_PATTERN.findall(output))
        if mentioned_actions != {facts.recommended_action}:
            violations.append(
                "changed_recommended_action:"
                + ",".join(sorted(mentioned_actions or {"missing"}))
            )
        return violations

    def _anomaly_changes(self, facts: CanonicalAuditFacts, output: str) -> list[str]:
        """异常类型不得丢失，也不得新增已知异常标签。"""

        allowed_labels = {ANOMALY_LABELS[item] for item in facts.anomaly_types}
        mentioned_labels = {
            label for label in ANOMALY_LABELS.values() if label in output
        }
        violations: list[str] = []
        missing = allowed_labels - mentioned_labels
        extra = mentioned_labels - allowed_labels
        if missing:
            violations.append("missing_anomaly_type:" + ",".join(sorted(missing)))
        if extra:
            violations.append("unknown_anomaly_type:" + ",".join(sorted(extra)))
        return violations
