"""审计报告输出模型。"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from procureguard.models.status import RecommendedAction, RiskLevel


class EvidenceItem(BaseModel):
    """审计报告里的证据项。"""

    field: str
    invoice_value: Any
    received_value: Any | None = None
    expected_value: Any | None = None


class ExplanationMetadata(BaseModel):
    """Phase 3H 向后兼容的可选解释元数据。"""

    explanation_text: str
    explanation_source: Literal["template", "controlled_rewrite"]
    explanation_mode: Literal["template", "shadow", "experimental"]
    facts_hash: str
    template_version: str
    prompt_version: str
    model_version: str
    adapter_version: str
    raw_llm_output: str | None = None
    used_rewrite: bool
    fallback_reason: str | None = None
    guard_passed: bool
    guard_violations: list[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    """最终业务结构化输出。"""

    invoice_id: str
    vendor: str
    total_amount: float
    currency: str
    po_match: bool
    goods_receipt_match: bool
    policy_flags: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    recommended_action: RecommendedAction
    evidence: list[EvidenceItem] = Field(default_factory=list)
    anomaly_explanation: str
    trace_id: str
    explanation: ExplanationMetadata | None = None
