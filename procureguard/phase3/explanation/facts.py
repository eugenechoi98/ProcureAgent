"""Canonical Audit Facts 适配层，作为解释生成的唯一事实来源。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from procureguard.phase3.schemas import AnomalyType, InputFacts


class FrozenJsonObject(Mapping[str, Any]):
    """递归不可变 JSON 对象，仅提供只读 Mapping 接口。"""

    __slots__ = ("_items",)

    def __init__(self, value: Mapping[str, Any]) -> None:
        object.__setattr__(
            self,
            "_items",
            tuple((str(key), freeze_json(item)) for key, item in value.items()),
        )

    def __getitem__(self, key: str) -> Any:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("FrozenJsonObject 不允许修改")

    def __delattr__(self, name: str) -> None:
        raise TypeError("FrozenJsonObject 不允许修改")

    def to_json_value(self) -> dict[str, Any]:
        """转换为可审计序列化的普通 JSON 对象。"""

        return {key: thaw_json(value) for key, value in self._items}


def freeze_json(value: Any) -> Any:
    """递归冻结 dict/list，防止共享引用被下游原地修改。"""

    if isinstance(value, FrozenJsonObject):
        return value
    if isinstance(value, Mapping):
        return FrozenJsonObject(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("evidence 只允许 JSON 对象、数组和基础值")


def thaw_json(value: Any) -> Any:
    """把不可变快照转换为 JSON 可序列化结构。"""

    if isinstance(value, FrozenJsonObject):
        return value.to_json_value()
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


class CanonicalAuditFacts(BaseModel):
    """解释层只读事实契约，不修改 Phase 2 共享 schema。"""

    model_config = ConfigDict(
        extra="forbid", frozen=True, arbitrary_types_allowed=True
    )

    invoice_id: str | None = None
    vendor_name: str | None = None
    invoice_number: str | None = None
    po_number: str | None = None
    grn_number: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    anomaly_types: tuple[AnomalyType, ...] = Field(default_factory=tuple)
    evidence: tuple[FrozenJsonObject, ...] = Field(default_factory=tuple)
    missing_fields: tuple[str, ...] = Field(default_factory=tuple)
    risk_level: Literal["low", "medium", "high"]
    recommended_action: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    policy_flags: tuple[str, ...] = Field(default_factory=tuple)
    source: str = "phase2_canonical_audit_facts"

    @field_validator("anomaly_types", mode="before")
    @classmethod
    def freeze_anomaly_types(cls, value: Any) -> tuple[Any, ...]:
        """异常类型转成 tuple，禁止 append、remove 和元素替换。"""

        return tuple(value)

    @field_validator("missing_fields", "policy_flags", mode="before")
    @classmethod
    def freeze_unique_strings(cls, value: Any) -> tuple[str, ...]:
        """字符串列表去重后转成 tuple，保持稳定顺序。"""

        return tuple(dict.fromkeys(item for item in value if item))

    @field_validator("evidence", mode="before")
    @classmethod
    def freeze_evidence(cls, value: Any) -> tuple[FrozenJsonObject, ...]:
        """evidence 及其嵌套 dict/list 递归冻结。"""

        return tuple(
            item if isinstance(item, FrozenJsonObject) else FrozenJsonObject(item)
            for item in value
        )

    @field_serializer("evidence")
    def serialize_evidence(
        self, value: tuple[FrozenJsonObject, ...]
    ) -> list[dict[str, Any]]:
        """审计输出仍使用普通 JSON 数组和对象。"""

        return [item.to_json_value() for item in value]

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
