"""Phase 3K 证据目录、引用约束校验、确定性渲染与安全回退。"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from procureguard.phase3.dataset import ANOMALY_LABELS
from procureguard.phase3.explanation.facts import CanonicalAuditFacts, thaw_json
from procureguard.phase3.explanation.renderer import DeterministicTemplateRenderer
from procureguard.phase3.schemas import AnomalyType

IDENTIFIER_PATTERN = re.compile(r"\b(?:PO|GRN|INV)-[A-Za-z0-9-]+\b", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"\b(?:USD|EUR|GBP|CNY)?\s*([0-9][0-9,]*\.\d{2})\b")
APPROVER_PATTERN = re.compile(r"审批人|CFO|财务总监|采购经理")
VENDOR_PATTERN = re.compile(r"供应商\s+([^，。；]+)")


class EvidenceSourceType(str, Enum):
    """允许的证据来源。"""

    INVOICE = "invoice"
    PO = "po"
    GRN = "grn"
    DUPLICATE_CHECK = "duplicate_check"
    POLICY = "policy"
    RISK_RULE = "risk_rule"
    AUDIT_FACT = "audit_fact"


class ClaimType(str, Enum):
    """Phase 3K 保守支持的声明类型。"""

    INVOICE_ID = "invoice_id"
    PO_REFERENCE = "po_reference"
    GRN_REFERENCE = "grn_reference"
    AMOUNT_FACT = "amount_fact"
    AMOUNT_MISMATCH = "amount_mismatch"
    VENDOR_FACT = "vendor_fact"
    POLICY_RULE = "policy_rule"
    RISK_LEVEL = "risk_level"
    RECOMMENDED_ACTION = "recommended_action"
    ANOMALY = "anomaly"
    MISSING_FIELD = "missing_field"
    DUPLICATE_INVOICE = "duplicate_invoice"


class EvidenceItem(BaseModel):
    """仅由上游确定事实构造的稳定证据项。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    source_type: EvidenceSourceType
    field_name: str
    value: str
    normalized_value: str
    allowed_claim_types: tuple[ClaimType, ...]
    display_text: str


class EvidenceCatalog(BaseModel):
    """不可变证据目录，display_text 不作为事实真源。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts_hash: str
    items: tuple[EvidenceItem, ...]

    def by_id(self) -> dict[str, EvidenceItem]:
        """按稳定 ID 返回证据映射。"""

        return {item.evidence_id: item for item in self.items}


class CitationBullet(BaseModel):
    """带声明类型和证据引用的低风险说明。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_type: ClaimType
    text: str = Field(min_length=2, max_length=300)
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def freeze_ids(cls, value: Any) -> tuple[str, ...]:
        """证据 ID 稳定去重。"""

        return tuple(dict.fromkeys(value))


class CitationStructuredExplanation(BaseModel):
    """Phase 3K 独立 citation-grounded structured schema。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    anomaly_types: tuple[AnomalyType, ...]
    missing_fields: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    risk_level_copy: Literal["low", "medium", "high"]
    recommended_action_copy: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    explanation_bullets: tuple[CitationBullet, ...] = Field(min_length=1)

    @field_validator(
        "anomaly_types", "missing_fields", "cited_evidence_ids", mode="before"
    )
    @classmethod
    def freeze_unique(cls, value: Any) -> tuple[Any, ...]:
        """集合字段稳定去重。"""

        return tuple(dict.fromkeys(value))


class CitationValidationResult(BaseModel):
    """引用校验的 fail-closed 结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    reject_reasons: tuple[str, ...] = ()
    invalid_evidence_ids: tuple[str, ...] = ()
    mismatched_claims: tuple[str, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    missing_citations: tuple[str, ...] = ()


class ValidatedCitationExplanation(BaseModel):
    """只有 ClaimEvidenceValidator 能生成的渲染输入。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation: CitationStructuredExplanation
    facts_hash: str
    catalog_hash: str


class CitationExplanationResult(BaseModel):
    """Phase 3K 离线服务结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["accepted", "rejected"]
    rendered_text: str
    fallback_used: bool
    validation: CitationValidationResult


def build_evidence_catalog(facts: CanonicalAuditFacts) -> EvidenceCatalog:
    """只从 Canonical Audit Facts 构造稳定目录。"""

    items: list[EvidenceItem] = []

    def add(
        evidence_id: str,
        source_type: EvidenceSourceType,
        field_name: str,
        value: object,
        claim_types: tuple[ClaimType, ...],
        label: str,
    ) -> None:
        normalized = _normalize(value)
        items.append(
            EvidenceItem(
                evidence_id=evidence_id,
                source_type=source_type,
                field_name=field_name,
                value=str(value),
                normalized_value=normalized,
                allowed_claim_types=claim_types,
                display_text=f"{label}: {value}",
            )
        )

    if facts.vendor_name:
        add("invoice.vendor_name", EvidenceSourceType.INVOICE, "vendor_name", facts.vendor_name, (ClaimType.VENDOR_FACT,), "发票供应商")
    if facts.invoice_number:
        add("invoice.invoice_number", EvidenceSourceType.INVOICE, "invoice_number", facts.invoice_number, (ClaimType.INVOICE_ID,), "发票号")
    if facts.total_amount is not None:
        add("invoice.total_amount", EvidenceSourceType.INVOICE, "total_amount", f"{facts.total_amount:.2f}", (ClaimType.AMOUNT_FACT, ClaimType.AMOUNT_MISMATCH), "发票金额")
    if facts.po_number:
        add("po.number", EvidenceSourceType.PO, "po_number", facts.po_number, (ClaimType.PO_REFERENCE,), "采购订单号")
    if facts.grn_number:
        add("grn.number", EvidenceSourceType.GRN, "grn_number", facts.grn_number, (ClaimType.GRN_REFERENCE,), "收货单号")
    for field in facts.missing_fields:
        source = EvidenceSourceType.PO if field == "po_number" else EvidenceSourceType.GRN if field == "grn_number" else EvidenceSourceType.AUDIT_FACT
        add(f"missing.{field}", source, field, "missing", (ClaimType.MISSING_FIELD,), f"缺失字段 {field}")
    for anomaly in facts.anomaly_types:
        claim_types = (ClaimType.ANOMALY,)
        if anomaly == AnomalyType.DUPLICATE_INVOICE:
            claim_types = (ClaimType.ANOMALY, ClaimType.DUPLICATE_INVOICE)
        add(f"anomaly.{anomaly.value}", EvidenceSourceType.AUDIT_FACT, "anomaly_type", anomaly.value, claim_types, "异常类型")
    for index, frozen in enumerate(facts.evidence, start=1):
        item = thaw_json(frozen)
        field = str(item.get("field", "evidence"))
        if field == "total_amount":
            for key, evidence_id, source in (("expected_value", "po.total_amount", EvidenceSourceType.PO), ("diff", "audit.amount_diff", EvidenceSourceType.AUDIT_FACT)):
                if item.get(key) is not None:
                    add(evidence_id, source, key, f"{float(item[key]):.2f}", (ClaimType.AMOUNT_FACT, ClaimType.AMOUNT_MISMATCH), key)
        elif field == "duplicate_invoice":
            add("duplicate_check.match", EvidenceSourceType.DUPLICATE_CHECK, field, item.get("invoice_value", "matched"), (ClaimType.DUPLICATE_INVOICE,), "重复检查命中")
        else:
            add(f"audit.evidence.{index:03d}", EvidenceSourceType.AUDIT_FACT, field, _stable_item_value(item), (ClaimType.ANOMALY,), "审核证据")
    for index, flag in enumerate(facts.policy_flags, start=1):
        add(f"policy.rule.{index:03d}", EvidenceSourceType.POLICY, "policy_flag", flag, (ClaimType.POLICY_RULE,), "政策规则")
    add("risk.level", EvidenceSourceType.RISK_RULE, "risk_level", facts.risk_level, (ClaimType.RISK_LEVEL,), "风险等级")
    add("action.recommended", EvidenceSourceType.RISK_RULE, "recommended_action", facts.recommended_action, (ClaimType.RECOMMENDED_ACTION,), "建议动作")
    return EvidenceCatalog(facts_hash=facts.facts_hash(), items=tuple(items))


class ClaimEvidenceValidator:
    """保守校验 claim type、引用关系与关键事实一致性。"""

    def validate(
        self,
        facts: CanonicalAuditFacts,
        catalog: EvidenceCatalog,
        explanation: CitationStructuredExplanation,
    ) -> tuple[CitationValidationResult, ValidatedCitationExplanation | None]:
        """任一引用无法证明就拒绝。"""

        reasons: list[str] = []
        invalid: list[str] = []
        mismatched: list[str] = []
        unsupported: list[str] = []
        missing: list[str] = []
        by_id = catalog.by_id()
        if catalog.facts_hash != facts.facts_hash():
            reasons.append("catalog_facts_hash_mismatch")
        if set(item.value for item in explanation.anomaly_types) != set(item.value for item in facts.anomaly_types):
            reasons.append("anomaly_types_mismatch")
        if set(explanation.missing_fields) != set(facts.missing_fields):
            reasons.append("missing_fields_mismatch")
        if explanation.risk_level_copy != facts.risk_level:
            reasons.append("risk_level_copy_mismatch")
        if explanation.recommended_action_copy != facts.recommended_action:
            reasons.append("recommended_action_copy_mismatch")
        bullet_union: set[str] = set()
        covered_anomalies: set[str] = set()
        for index, bullet in enumerate(explanation.explanation_bullets, start=1):
            if not bullet.evidence_ids:
                missing.append(f"bullet_{index}")
                continue
            bullet_union.update(bullet.evidence_ids)
            bound = []
            for evidence_id in bullet.evidence_ids:
                item = by_id.get(evidence_id)
                if item is None:
                    invalid.append(evidence_id)
                else:
                    bound.append(item)
            if bound and not any(bullet.claim_type in item.allowed_claim_types for item in bound):
                mismatched.append(f"claim_type_not_allowed:bullet_{index}")
            claim_failures = self._ground_claim(facts, bullet, bound, index)
            mismatched.extend(claim_failures[0])
            unsupported.extend(claim_failures[1])
            if bullet.claim_type in (ClaimType.ANOMALY, ClaimType.DUPLICATE_INVOICE):
                covered_anomalies.update(
                    item.normalized_value
                    for item in bound
                    if item.field_name == "anomaly_type"
                )
        if set(explanation.cited_evidence_ids) != bullet_union:
            reasons.append("cited_evidence_ids_mismatch")
        expected_anomalies = {item.value for item in facts.anomaly_types}
        if not expected_anomalies <= covered_anomalies:
            reasons.append("anomaly_citation_missing")
        if invalid:
            reasons.append("invalid_evidence_ids")
        if missing:
            reasons.append("missing_citations")
        if mismatched:
            reasons.append("mismatched_evidence_claim")
        if unsupported:
            reasons.append("unsupported_claims")
        reasons = list(dict.fromkeys(reasons))
        result = CitationValidationResult(
            passed=not reasons,
            reject_reasons=tuple(reasons),
            invalid_evidence_ids=tuple(dict.fromkeys(invalid)),
            mismatched_claims=tuple(dict.fromkeys(mismatched)),
            unsupported_claims=tuple(dict.fromkeys(unsupported)),
            missing_citations=tuple(dict.fromkeys(missing)),
        )
        if not result.passed:
            return result, None
        catalog_hash = "|".join(item.evidence_id for item in catalog.items)
        return result, ValidatedCitationExplanation(explanation=explanation, facts_hash=facts.facts_hash(), catalog_hash=catalog_hash)

    def _ground_claim(
        self, facts: CanonicalAuditFacts, bullet: CitationBullet, bound: list[EvidenceItem], index: int
    ) -> tuple[list[str], list[str]]:
        """关键实体必须出现在当前 bullet 绑定的证据中。"""

        mismatched: list[str] = []
        unsupported: list[str] = []
        values = {item.normalized_value for item in bound}
        text = bullet.text
        for identifier in IDENTIFIER_PATTERN.findall(text):
            if _normalize(identifier) not in values:
                mismatched.append(f"identifier_not_grounded:bullet_{index}:{identifier}")
        for amount in AMOUNT_PATTERN.findall(text):
            normalized = _normalize(amount)
            if not any(normalized == value or normalized in value for value in values):
                mismatched.append(f"amount_not_grounded:bullet_{index}:{amount}")
        for vendor in VENDOR_PATTERN.findall(text):
            if _normalize(vendor.strip()) not in values:
                mismatched.append(f"vendor_not_grounded:bullet_{index}")
        if APPROVER_PATTERN.search(text) and not any(item.source_type == EvidenceSourceType.POLICY and _normalize(APPROVER_PATTERN.search(text).group(0)) in item.normalized_value for item in bound):
            unsupported.append(f"approver_not_grounded:bullet_{index}")
        if bullet.claim_type == ClaimType.RISK_LEVEL and _normalize(facts.risk_level) not in values:
            mismatched.append(f"risk_not_grounded:bullet_{index}")
        if bullet.claim_type == ClaimType.RECOMMENDED_ACTION and _normalize(facts.recommended_action) not in values:
            mismatched.append(f"action_not_grounded:bullet_{index}")
        if bullet.claim_type == ClaimType.POLICY_RULE and not any(item.source_type == EvidenceSourceType.POLICY for item in bound):
            mismatched.append(f"policy_not_grounded:bullet_{index}")
        if bullet.claim_type == ClaimType.DUPLICATE_INVOICE and not any(item.source_type == EvidenceSourceType.DUPLICATE_CHECK for item in bound):
            mismatched.append(f"duplicate_not_grounded:bullet_{index}")
        if bound and not any(item.normalized_value in _normalize(text) or item.field_name.replace("_", "") in _normalize(text) for item in bound):
            mismatched.append(f"citation_unrelated:bullet_{index}")
        return mismatched, unsupported


class CitationRenderer:
    """只渲染通过 citation validator 的输出。"""

    version = "phase3k-citation-renderer-v1"

    def render(self, facts: CanonicalAuditFacts, catalog: EvidenceCatalog, validated: ValidatedCitationExplanation) -> str:
        """稳定显示引用 ID，不重新推断或补全证据。"""

        if not isinstance(validated, ValidatedCitationExplanation):
            raise TypeError("renderer 只接受 ValidatedCitationExplanation")
        if validated.facts_hash != facts.facts_hash() or catalog.facts_hash != facts.facts_hash():
            raise ValueError("validated citation 与当前 facts 不匹配")
        lines = ["引用约束审核说明："]
        for bullet in validated.explanation.explanation_bullets:
            lines.append(f"- {bullet.text} [evidence: {', '.join(bullet.evidence_ids)}]")
        lines.extend((f"风险等级：{validated.explanation.risk_level_copy}", f"建议动作：{validated.explanation.recommended_action_copy}"))
        return "\n".join(lines)


class CitationExplanationService:
    """Phase 3K 离线入口，失败时返回无 citation 标记的原模板。"""

    def __init__(self) -> None:
        self.validator = ClaimEvidenceValidator()
        self.renderer = CitationRenderer()
        self.template_renderer = DeterministicTemplateRenderer()

    def explain(self, facts: CanonicalAuditFacts, catalog: EvidenceCatalog, payload: Any) -> CitationExplanationResult:
        """解析、校验和渲染，任一失败都 fail-closed。"""

        try:
            candidate = CitationStructuredExplanation.model_validate(payload)
        except (ValidationError, ValueError, TypeError) as exc:
            validation = CitationValidationResult(passed=False, reject_reasons=(f"schema_invalid:{exc.__class__.__name__}",))
            return CitationExplanationResult(status="rejected", rendered_text=self.template_renderer.render(facts), fallback_used=True, validation=validation)
        validation, validated = self.validator.validate(facts, catalog, candidate)
        if validated is None:
            return CitationExplanationResult(status="rejected", rendered_text=self.template_renderer.render(facts), fallback_used=True, validation=validation)
        return CitationExplanationResult(status="accepted", rendered_text=self.renderer.render(facts, catalog, validated), fallback_used=False, validation=validation)


def build_rule_only_citation_explanation(facts: CanonicalAuditFacts, catalog: EvidenceCatalog) -> CitationStructuredExplanation:
    """从事实和目录直接构造不训练模型的 citation baseline。"""

    bullets: list[CitationBullet] = []
    catalog_ids = catalog.by_id()
    if "invoice.vendor_name" in catalog_ids:
        bullets.append(CitationBullet(claim_type=ClaimType.VENDOR_FACT, text=f"发票供应商 {facts.vendor_name}。", evidence_ids=("invoice.vendor_name",)))
    if "po.number" in catalog_ids:
        bullets.append(CitationBullet(claim_type=ClaimType.PO_REFERENCE, text=f"采购订单 {facts.po_number}。", evidence_ids=("po.number",)))
    if "grn.number" in catalog_ids:
        bullets.append(CitationBullet(claim_type=ClaimType.GRN_REFERENCE, text=f"收货单 {facts.grn_number}。", evidence_ids=("grn.number",)))
    if "po.total_amount" in catalog_ids and "invoice.total_amount" in catalog_ids:
        invoice_amount = catalog_ids["invoice.total_amount"].value
        po_amount = catalog_ids["po.total_amount"].value
        bullets.append(CitationBullet(claim_type=ClaimType.AMOUNT_MISMATCH, text=f"发票金额 {invoice_amount} 与 PO 金额 {po_amount} 不一致。", evidence_ids=("invoice.total_amount", "po.total_amount")))
    for item in catalog.items:
        if item.source_type == EvidenceSourceType.POLICY:
            bullets.append(CitationBullet(claim_type=ClaimType.POLICY_RULE, text=f"政策规则 {item.value}。", evidence_ids=(item.evidence_id,)))
    for anomaly in facts.anomaly_types:
        ids = [f"anomaly.{anomaly.value}"]
        claim_type = ClaimType.DUPLICATE_INVOICE if anomaly == AnomalyType.DUPLICATE_INVOICE and "duplicate_check.match" in catalog.by_id() else ClaimType.ANOMALY
        if claim_type == ClaimType.DUPLICATE_INVOICE:
            ids.append("duplicate_check.match")
        bullets.append(CitationBullet(claim_type=claim_type, text=f"检测到{ANOMALY_LABELS[anomaly]}（{anomaly.value}）。", evidence_ids=tuple(ids)))
    for field in facts.missing_fields:
        bullets.append(CitationBullet(claim_type=ClaimType.MISSING_FIELD, text=f"字段 {field} 缺失（missing）。", evidence_ids=(f"missing.{field}",)))
    bullets.append(CitationBullet(claim_type=ClaimType.RISK_LEVEL, text=f"风险等级为 {facts.risk_level}。", evidence_ids=("risk.level",)))
    bullets.append(CitationBullet(claim_type=ClaimType.RECOMMENDED_ACTION, text=f"建议动作是 {facts.recommended_action}。", evidence_ids=("action.recommended",)))
    cited = tuple(dict.fromkeys(evidence_id for bullet in bullets for evidence_id in bullet.evidence_ids))
    return CitationStructuredExplanation(anomaly_types=facts.anomaly_types, missing_fields=facts.missing_fields, cited_evidence_ids=cited, risk_level_copy=facts.risk_level, recommended_action_copy=facts.recommended_action, explanation_bullets=tuple(bullets))


def _normalize(value: object) -> str:
    """统一证据与 claim 的比较形式。"""

    text = str(value).strip().lower().replace(",", "")
    try:
        return f"{float(text):.2f}"
    except ValueError:
        return re.sub(r"\s+", "", text)


def _stable_item_value(item: dict[str, Any]) -> str:
    """把通用 evidence 转成稳定、只读的值。"""

    return "|".join(f"{key}={item[key]}" for key in sorted(item))
