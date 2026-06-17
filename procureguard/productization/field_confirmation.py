"""Phase 4G 字段确认层：模型候选转人工确认后的审计事实。"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from procureguard.models.invoice import ExtractedFields, LineItem


CanonicalField = Literal[
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "total_amount",
    "currency",
    "po_number",
    "line_items",
]
DecisionAction = Literal["accept", "correct", "reject", "missing"]
GovernanceStatus = Literal["auto_accepted", "needs_review", "must_confirm", "rejected"]

FIELD_ALIASES = {
    "company": "vendor_name",
    "vendor_name": "vendor_name",
    "date": "invoice_date",
    "invoice_date": "invoice_date",
    "total": "total_amount",
    "total_amount": "total_amount",
    "invoice_number": "invoice_number",
    "currency": "currency",
    "po_number": "po_number",
    "line_items": "line_items",
}
CRITICAL_FIELDS = {"invoice_number", "total_amount", "vendor_name", "invoice_date"}
AUDIT_REQUIRED_FIELDS = {
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "total_amount",
    "currency",
    "po_number",
}


class FieldCandidate(BaseModel):
    """LayoutLMv3 字段候选，不是审计事实。"""

    model_config = ConfigDict(extra="forbid")
    field_name: str = Field(min_length=1)
    predicted_value: Any | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    token_spans: list[dict[str, Any]] = Field(default_factory=list)
    bbox_list: list[list[int]] = Field(default_factory=list)
    source: Literal["live_layoutlmv3"]
    requires_human_confirmation: bool = True
    warning: str | None = None
    failure_reason: str | None = None

    @field_validator("field_name")
    @classmethod
    def normalize_field_name(cls, value: str) -> str:
        """统一候选字段名。"""

        normalized = value.strip().lower()
        if normalized not in FIELD_ALIASES:
            raise ValueError(f"unsupported candidate field_name: {value}")
        return normalized

    @property
    def canonical_name(self) -> str:
        """映射到 ExtractedFields 的字段名。"""

        return FIELD_ALIASES[self.field_name]


class FieldDecision(BaseModel):
    """人工确认、修正、拒绝或声明缺失。"""

    model_config = ConfigDict(extra="forbid")
    field_name: CanonicalField
    action: DecisionAction
    value: Any | None = None
    reviewer_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_value_for_action(self) -> "FieldDecision":
        """accept/correct 必须给出非空值，reject/missing 不得伪造值。"""

        if self.action in {"accept", "correct"} and _is_blank(self.value):
            raise ValueError("accept/correct decisions require a non-blank value")
        if self.action in {"reject", "missing"} and self.value is not None:
            raise ValueError("reject/missing decisions must not carry a value")
        return self


class ConfirmationLineItem(BaseModel):
    """确认后的行项目。"""

    model_config = ConfigDict(extra="forbid")
    item: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, ge=0)


class FieldConfirmationRequest(BaseModel):
    """字段确认请求。"""

    model_config = ConfigDict(extra="forbid")
    candidates: list[FieldCandidate] = Field(default_factory=list)
    decisions: list[FieldDecision] = Field(default_factory=list)
    confirmation_mode: Literal["human", "simulated_human"] = "human"
    trace_id: str | None = None

    @model_validator(mode="after")
    def require_decisions(self) -> "FieldConfirmationRequest":
        """不允许把 raw model candidate 当作确认结果。"""

        if not self.decisions:
            raise ValueError("confirmed field decisions are required; model candidates cannot bypass confirmation")
        return self


class FieldGovernanceRecord(BaseModel):
    """单字段治理状态和来源。"""

    field_name: str
    canonical_field: str
    confidence: float | None
    status: GovernanceStatus
    source: str
    requires_human_confirmation: bool
    decision_action: DecisionAction | None = None
    used_for_audit: bool = False
    reason: str


class ConfirmedAuditInput(BaseModel):
    """Phase 2 唯一允许接收的确认后事实输入。"""

    model_config = ConfigDict(extra="forbid")
    confirmed_fields: ExtractedFields
    confirmation_trace: list[FieldGovernanceRecord]
    corrected_fields: dict[str, Any] = Field(default_factory=dict)
    rejected_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    source: Literal["confirmed_fields"] = "confirmed_fields"
    raw_model_bypass_allowed: Literal[False] = False
    risk_decision_source: Literal["deterministic_rules_only"] = "deterministic_rules_only"


class FieldConfirmationResponse(BaseModel):
    """字段确认响应，不包含风险或建议动作。"""

    status: Literal["confirmed", "incomplete"]
    confirmed_fields: dict[str, Any]
    corrected_fields: dict[str, Any]
    rejected_fields: list[str]
    missing_fields: list[str]
    governance: list[FieldGovernanceRecord]
    audit_input: ConfirmedAuditInput | None
    phase2_invoked: Literal[False] = False
    risk_level_generated: Literal[False] = False
    recommended_action_generated: Literal[False] = False


def confirm_fields(request: FieldConfirmationRequest) -> FieldConfirmationResponse:
    """执行字段确认，不运行 Phase 2。"""

    candidates = {candidate.canonical_name: candidate for candidate in request.candidates}
    decisions = {decision.field_name: decision for decision in request.decisions}
    governance: list[FieldGovernanceRecord] = []
    confirmed: dict[str, Any] = {}
    corrected: dict[str, Any] = {}
    rejected: list[str] = []
    missing: list[str] = []

    for canonical in sorted(set(candidates) | set(decisions) | AUDIT_REQUIRED_FIELDS):
        candidate = candidates.get(canonical)
        decision = decisions.get(canonical)
        status = _governance_status(canonical, candidate)
        if decision is None:
            if canonical in AUDIT_REQUIRED_FIELDS:
                missing.append(canonical)
            governance.append(_record(canonical, candidate, status, None, False, "no human decision"))
            continue
        if decision.action in {"accept", "correct"}:
            value = _normalize_confirmed_value(canonical, decision.value)
            confirmed[canonical] = value
            if decision.action == "correct" or (candidate and value != candidate.predicted_value):
                corrected[canonical] = value
            governance.append(_record(canonical, candidate, status, decision, True, "human confirmed"))
        elif decision.action == "reject":
            rejected.append(canonical)
            if canonical in AUDIT_REQUIRED_FIELDS:
                missing.append(canonical)
            governance.append(_record(canonical, candidate, "rejected", decision, False, "human rejected"))
        else:
            missing.append(canonical)
            governance.append(_record(canonical, candidate, status, decision, False, "human marked missing"))

    missing = sorted(set(missing) - set(confirmed))
    if AUDIT_REQUIRED_FIELDS.issubset(confirmed):
        extracted = ExtractedFields(
            vendor_name=str(confirmed["vendor_name"]),
            invoice_number=str(confirmed["invoice_number"]),
            invoice_date=_date_to_text(confirmed["invoice_date"]),
            po_number=str(confirmed["po_number"]),
            total_amount=float(confirmed["total_amount"]),
            currency=str(confirmed["currency"]).upper(),
            line_items=_line_items(confirmed.get("line_items")),
            extraction_confidence=1.0,
            extraction_model="confirmed_fields_from_layoutlmv3_candidates",
        )
        audit_input = ConfirmedAuditInput(
            confirmed_fields=extracted,
            confirmation_trace=governance,
            corrected_fields=corrected,
            rejected_fields=sorted(set(rejected)),
            missing_fields=missing,
        )
        status: Literal["confirmed", "incomplete"] = "confirmed"
    else:
        audit_input = None
        status = "incomplete"

    return FieldConfirmationResponse(
        status=status,
        confirmed_fields=confirmed,
        corrected_fields=corrected,
        rejected_fields=sorted(set(rejected)),
        missing_fields=missing,
        governance=governance,
        audit_input=audit_input,
    )


def confirmed_audit_input_to_extracted_fields(audit_input: ConfirmedAuditInput) -> ExtractedFields:
    """Phase 2 集成只从 ConfirmedAuditInput 取 ExtractedFields。"""

    if audit_input.source != "confirmed_fields" or audit_input.raw_model_bypass_allowed:
        raise ValueError("Phase 2 requires confirmed_fields; raw model output cannot bypass confirmation")
    return audit_input.confirmed_fields


def _governance_status(field: str, candidate: FieldCandidate | None) -> GovernanceStatus:
    if field in CRITICAL_FIELDS:
        return "must_confirm"
    if candidate is None or candidate.confidence is None:
        return "needs_review"
    if candidate.confidence >= 0.95 and not candidate.requires_human_confirmation:
        return "auto_accepted"
    if candidate.confidence >= 0.80:
        return "needs_review"
    return "must_confirm"


def _record(
    canonical: str,
    candidate: FieldCandidate | None,
    status: GovernanceStatus,
    decision: FieldDecision | None,
    used_for_audit: bool,
    reason: str,
) -> FieldGovernanceRecord:
    return FieldGovernanceRecord(
        field_name=candidate.field_name if candidate else canonical,
        canonical_field=canonical,
        confidence=candidate.confidence if candidate else None,
        status=status,
        source=candidate.source if candidate else "human_supplied_or_missing",
        requires_human_confirmation=True if candidate is None else candidate.requires_human_confirmation,
        decision_action=decision.action if decision else None,
        used_for_audit=used_for_audit,
        reason=reason,
    )


def _normalize_confirmed_value(field: str, value: Any) -> Any:
    if field == "total_amount":
        return float(value)
    if field == "currency":
        normalized = str(value).strip().upper()
        if len(normalized) != 3 or not normalized.isalpha() or not normalized.isascii():
            raise ValueError("currency must be a three-letter ASCII code")
        return normalized
    if field == "invoice_date":
        return _date_to_text(value)
    if field == "line_items":
        return value
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} must not be blank")
    return text


def _date_to_text(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _line_items(value: Any) -> list[LineItem]:
    if value is None:
        return []
    return [LineItem(**item) if isinstance(item, dict) else item for item in value]


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
