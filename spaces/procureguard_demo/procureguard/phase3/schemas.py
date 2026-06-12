"""Phase 3 独立训练数据契约，不修改共享业务 schema。"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnomalyType(str, Enum):
    """Phase 3 支持的异常类型。"""

    QUANTITY_MISMATCH = "quantity_mismatch"
    AMOUNT_DISCREPANCY = "amount_discrepancy"
    DUPLICATE_INVOICE = "duplicate_invoice"
    MISSING_PO_NUMBER = "missing_po_number"
    VENDOR_NAME_MISMATCH = "vendor_name_mismatch"
    MISSING_GOODS_RECEIPT = "missing_goods_receipt"
    HIGH_VALUE_APPROVAL_REQUIRED = "high_value_approval_required"
    MULTI_ISSUE_COMBINATION = "multi_issue_combination"


class InputFacts(BaseModel):
    """只保存 Phase 2 已确定的事实，模型不得重新计算或改写。"""

    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    invoice_number: str
    po_number: str | None = None
    grn_number: str | None = None
    total_amount: float = Field(gt=0)
    currency: Literal["USD", "EUR", "GBP", "CNY"]
    risk_level: Literal["low", "medium", "high"]
    recommended_action: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    policy_flags: list[str] = Field(default_factory=list)
    duplicate_check: bool
    po_match: bool
    grn_match: bool
    amount_match: bool
    mismatches: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    anomaly_types: list[AnomalyType] = Field(min_length=1)


class AnomalySample(BaseModel):
    """LoRA SFT 单条样本的独立契约。"""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    anomaly_type: AnomalyType
    input_facts: InputFacts
    expected_explanation: str = Field(min_length=20)
    risk_level: Literal["low", "medium", "high"]
    recommended_action: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    split: Literal["train", "validation", "test"]
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def validate_deterministic_outputs(self) -> "AnomalySample":
        """确保顶层训练标签与确定性输入事实完全一致。"""

        if self.risk_level != self.input_facts.risk_level:
            raise ValueError("risk_level 必须来自 input_facts")
        if self.recommended_action != self.input_facts.recommended_action:
            raise ValueError("recommended_action 必须来自 input_facts")
        included = set(self.input_facts.anomaly_types)
        if self.anomaly_type == AnomalyType.MULTI_ISSUE_COMBINATION:
            if len(included) < 2:
                raise ValueError("multi_issue_combination 至少包含两个异常")
        elif included != {self.anomaly_type}:
            raise ValueError("单异常样本只能包含对应 anomaly_type")
        return self
