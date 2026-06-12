"""Canonical Audit Facts 适配层，作为解释生成的唯一事实来源。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from procureguard.phase3.schemas import AnomalyType, InputFacts


class CanonicalAuditFacts(BaseModel):
    """解释层只读事实契约，不修改 Phase 2 共享 schema。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invoice_id: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    po_number: str | None = None
    grn_number: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    anomaly_types: list[AnomalyType] = Field(min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"]
    recommended_action: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    policy_flags: list[str] = Field(default_factory=list)
    source: str = "phase2_canonical_audit_facts"

    @model_validator(mode="after")
    def deduplicate_ordered_lists(self) -> "CanonicalAuditFacts":
        """保持列表稳定，避免同一事实渲染出不同文本。"""

        object.__setattr__(
            self,
            "missing_fields",
            list(dict.fromkeys(item for item in self.missing_fields if item)),
        )
        object.__setattr__(
            self,
            "policy_flags",
            list(dict.fromkeys(item for item in self.policy_flags if item)),
        )
        return self

    @classmethod
    def from_input_facts(
        cls, facts: InputFacts, invoice_id: str | None = None
    ) -> "CanonicalAuditFacts":
        """把 Phase 3 训练事实适配成 Phase 3H 解释事实。"""

        missing_fields: list[str] = []
        if facts.po_number is None:
            missing_fields.append("po_number")
        if facts.grn_number is None:
            missing_fields.append("grn_number")
        evidence = list(facts.evidence)
        for mismatch in facts.mismatches:
            if mismatch not in evidence:
                evidence.append(mismatch)
        return cls(
            invoice_id=invoice_id,
            vendor_name=facts.vendor_name,
            invoice_number=facts.invoice_number,
            po_number=facts.po_number,
            grn_number=facts.grn_number,
            total_amount=facts.total_amount,
            currency=facts.currency,
            anomaly_types=facts.anomaly_types,
            evidence=evidence,
            missing_fields=missing_fields,
            risk_level=facts.risk_level,
            recommended_action=facts.recommended_action,
            policy_flags=facts.policy_flags,
        )

    def stable_payload(self) -> dict[str, Any]:
        """返回用于 hash 和模板渲染的稳定 JSON 结构。"""

        return self.model_dump(mode="json", exclude_none=False)

    def facts_hash(self) -> str:
        """计算事实 hash，审计时可确认解释是否来自同一输入。"""

        payload = json.dumps(
            self.stable_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def known_identifiers(self) -> set[str]:
        """列出允许出现在解释里的业务单号。"""

        return {
            value.upper()
            for value in (
                self.invoice_id,
                self.invoice_number,
                self.po_number,
                self.grn_number,
            )
            if value
        }

    def known_amounts(self) -> set[str]:
        """列出允许出现在解释里的金额数字。"""

        amounts: set[str] = set()
        if self.total_amount is not None:
            amounts.add(f"{self.total_amount:.2f}")
        for item in self.evidence:
            for value in item.values():
                if isinstance(value, float):
                    amounts.add(f"{value:.2f}")
                elif isinstance(value, int):
                    amounts.add(f"{float(value):.2f}")
        return amounts

    def known_vendors(self) -> set[str]:
        """列出允许出现在解释里的供应商名称。"""

        vendors = {self.vendor_name} if self.vendor_name else set()
        for item in self.evidence:
            if item.get("field") == "vendor_name":
                vendors.update(
                    str(value)
                    for value in (item.get("invoice_value"), item.get("expected_value"))
                    if value
                )
        return vendors
