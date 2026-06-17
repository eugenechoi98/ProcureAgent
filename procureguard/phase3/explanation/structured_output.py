"""Phase 3J 结构化解释契约、校验器、渲染器与安全回退。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from procureguard.phase3.dataset import ANOMALY_LABELS
from procureguard.phase3.explanation.facts import CanonicalAuditFacts, thaw_json
from procureguard.phase3.explanation.renderer import DeterministicTemplateRenderer
from procureguard.phase3.schemas import AnomalyType

IDENTIFIER_PATTERN = re.compile(r"\b(?:PO|GRN|INV)-[A-Za-z0-9-]+\b", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"\b(?:USD|EUR|GBP|CNY)\s+([0-9][0-9,]*\.\d{2})\b")
APPROVER_TERMS = ("审批人", "CFO", "财务总监", "采购经理", "政策第")


class StructuredExplanationBullet(BaseModel):
    """低风险语言字段，每条说明必须绑定至少一个证据 ID。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=2, max_length=300)
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def freeze_evidence_ids(cls, value: Any) -> tuple[str, ...]:
        """证据 ID 去重并冻结，防止校验后被修改。"""

        return tuple(dict.fromkeys(value))


class StructuredExplanation(BaseModel):
    """与业务主契约解耦的 Phase 3J 模型输出 schema。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    anomaly_types: tuple[AnomalyType, ...]
    missing_fields: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    risk_level_copy: Literal["low", "medium", "high"]
    recommended_action_copy: Literal[
        "auto_approve", "request_human_approval", "reject"
    ]
    explanation_bullets: tuple[StructuredExplanationBullet, ...] = Field(min_length=1)

    @field_validator(
        "anomaly_types", "missing_fields", "cited_evidence_ids", mode="before"
    )
    @classmethod
    def freeze_unique_values(cls, value: Any) -> tuple[Any, ...]:
        """集合字段稳定去重，便于复现与审计。"""

        return tuple(dict.fromkeys(value))


class EvidenceDescriptor(BaseModel):
    """由 Canonical Audit Facts 派生的允许证据目录。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    keywords: tuple[str, ...]


class StructuredValidationResult(BaseModel):
    """fail-closed 校验结果，不把非法文本包装成正式解释。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    reject_reasons: tuple[str, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    invalid_evidence_ids: tuple[str, ...] = ()
    action_mismatch: bool = False
    risk_level_mismatch: bool = False
    anomaly_missing: tuple[str, ...] = ()
    anomaly_extra: tuple[str, ...] = ()
    missing_field_missing: tuple[str, ...] = ()
    missing_field_extra: tuple[str, ...] = ()


class ValidatedStructuredExplanation(BaseModel):
    """只有 StructuredExplanationValidator 可以生成的渲染输入。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation: StructuredExplanation
    facts_hash: str


class StructuredExplanationResult(BaseModel):
    """离线 structured baseline 的最终结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["accepted", "rejected"]
    rendered_text: str
    fallback_used: bool
    validation: StructuredValidationResult


def build_evidence_catalog(
    facts: CanonicalAuditFacts,
) -> dict[str, EvidenceDescriptor]:
    """从只读事实生成稳定 evidence ID，不依赖模型。"""

    descriptors: list[EvidenceDescriptor] = []

    def add(evidence_id: str, *keywords: object) -> None:
        values = tuple(
            dict.fromkeys(str(item) for item in keywords if item not in (None, ""))
        )
        descriptors.append(EvidenceDescriptor(evidence_id=evidence_id, keywords=values))

    add("fact.vendor_name", "供应商", facts.vendor_name)
    add("fact.invoice_number", "发票", "发票号", facts.invoice_number)
    if facts.po_number:
        add("fact.po_number", "采购订单", "PO", facts.po_number)
    if facts.grn_number:
        add("fact.grn_number", "收货", "GRN", facts.grn_number)
    if facts.total_amount is not None:
        add(
            "fact.total_amount",
            "金额",
            facts.currency,
            f"{facts.total_amount:.2f}",
        )
    for field in facts.missing_fields:
        add(f"missing.{field}", field, _field_label(field), "缺失", "未提供")
    for anomaly in facts.anomaly_types:
        add(f"anomaly.{anomaly.value}", anomaly.value, ANOMALY_LABELS[anomaly])
    for index, item in enumerate(facts.evidence, start=1):
        plain = thaw_json(item)
        add(
            f"evidence.{index:03d}",
            plain.get("field"),
            *[value for value in plain.values() if isinstance(value, (str, int, float))],
        )
    for index, flag in enumerate(facts.policy_flags, start=1):
        add(f"policy.{index:03d}", "政策", flag)
    add("decision.risk_level", "风险", "风险等级", facts.risk_level)
    add(
        "decision.recommended_action",
        "建议动作",
        facts.recommended_action,
    )
    return {item.evidence_id: item for item in descriptors}


class StructuredExplanationValidator:
    """把 schema 输出与 Canonical Audit Facts 做确定性一致性校验。"""

    def validate(
        self, facts: CanonicalAuditFacts, explanation: StructuredExplanation
    ) -> tuple[StructuredValidationResult, ValidatedStructuredExplanation | None]:
        """任何不一致都拒绝，只有完整通过才返回可渲染对象。"""

        catalog = build_evidence_catalog(facts)
        allowed_ids = set(catalog)
        actual_anomalies = {item.value for item in explanation.anomaly_types}
        expected_anomalies = {item.value for item in facts.anomaly_types}
        actual_missing = set(explanation.missing_fields)
        expected_missing = set(facts.missing_fields)
        cited_ids = set(explanation.cited_evidence_ids)
        bullet_ids = {
            evidence_id
            for bullet in explanation.explanation_bullets
            for evidence_id in bullet.evidence_ids
        }
        invalid_ids = sorted((cited_ids | bullet_ids) - allowed_ids)
        unsupported = self._unsupported_claims(facts, explanation, catalog)
        reasons: list[str] = []
        action_mismatch = (
            explanation.recommended_action_copy != facts.recommended_action
        )
        risk_mismatch = explanation.risk_level_copy != facts.risk_level
        anomaly_missing = sorted(expected_anomalies - actual_anomalies)
        anomaly_extra = sorted(actual_anomalies - expected_anomalies)
        missing_field_missing = sorted(expected_missing - actual_missing)
        missing_field_extra = sorted(actual_missing - expected_missing)

        if risk_mismatch:
            reasons.append("risk_level_copy_mismatch")
        if action_mismatch:
            reasons.append("recommended_action_copy_mismatch")
        if anomaly_missing:
            reasons.append("anomaly_types_missing")
        if anomaly_extra:
            reasons.append("anomaly_types_extra")
        if missing_field_missing:
            reasons.append("missing_fields_omitted")
        if missing_field_extra:
            reasons.append("missing_fields_extra")
        if invalid_ids:
            reasons.append("invalid_evidence_ids")
        if cited_ids != bullet_ids:
            reasons.append("cited_evidence_ids_mismatch")
        if unsupported:
            reasons.append("unsupported_claims")
        reasons = list(dict.fromkeys(reasons))
        result = StructuredValidationResult(
            passed=not reasons,
            reject_reasons=tuple(reasons),
            unsupported_claims=tuple(unsupported),
            invalid_evidence_ids=tuple(invalid_ids),
            action_mismatch=action_mismatch,
            risk_level_mismatch=risk_mismatch,
            anomaly_missing=tuple(anomaly_missing),
            anomaly_extra=tuple(anomaly_extra),
            missing_field_missing=tuple(missing_field_missing),
            missing_field_extra=tuple(missing_field_extra),
        )
        if not result.passed:
            return result, None
        return result, ValidatedStructuredExplanation(
            explanation=explanation,
            facts_hash=facts.facts_hash(),
        )

    def _unsupported_claims(
        self,
        facts: CanonicalAuditFacts,
        explanation: StructuredExplanation,
        catalog: dict[str, EvidenceDescriptor],
    ) -> list[str]:
        """检查未知实体以及 bullet 与证据 ID 的明显不匹配。"""

        claims: list[str] = []
        known_identifiers = facts.known_identifiers()
        known_amounts = facts.known_amounts()
        known_vendors = facts.known_vendors()
        allowed_text = facts.model_dump_json(exclude_none=False)
        for bullet_index, bullet in enumerate(explanation.explanation_bullets):
            text = bullet.text
            for identifier in IDENTIFIER_PATTERN.findall(text):
                if identifier.upper() not in known_identifiers:
                    claims.append(f"unknown_identifier:{identifier}")
            for amount in AMOUNT_PATTERN.findall(text):
                if amount.replace(",", "") not in known_amounts:
                    claims.append(f"unknown_amount:{amount}")
            for term in APPROVER_TERMS:
                if term in text and term not in allowed_text:
                    claims.append(f"unsupported_policy_or_approver:{term}")
            vendor_claim = re.search(r"供应商\s+([^，。；]+)", text)
            if vendor_claim and "未提供" not in vendor_claim.group(1):
                claimed_vendor = vendor_claim.group(1).strip()
                if not any(claimed_vendor.startswith(vendor) for vendor in known_vendors):
                    claims.append(f"unknown_vendor:{claimed_vendor}")
            valid_descriptors = [
                catalog[evidence_id]
                for evidence_id in bullet.evidence_ids
                if evidence_id in catalog
            ]
            if valid_descriptors and not any(
                any(keyword.lower() in text.lower() for keyword in item.keywords)
                for item in valid_descriptors
            ):
                claims.append(f"evidence_claim_mismatch:bullet_{bullet_index + 1}")
        return list(dict.fromkeys(claims))


class StructuredExplanationRenderer:
    """仅渲染 validator 已确认通过的结构化解释。"""

    version = "phase3j-structured-renderer-v1"

    def render(
        self,
        facts: CanonicalAuditFacts,
        validated: ValidatedStructuredExplanation,
    ) -> str:
        """稳定输出中文说明，不重新推断上游结论。"""

        if not isinstance(validated, ValidatedStructuredExplanation):
            raise TypeError("renderer 只接受 ValidatedStructuredExplanation")
        if validated.facts_hash != facts.facts_hash():
            raise ValueError("validated explanation 与当前 facts 不匹配")
        item = validated.explanation
        anomalies = "、".join(ANOMALY_LABELS[value] for value in item.anomaly_types)
        missing = "、".join(_field_label(value) for value in item.missing_fields) or "无"
        bullets = "\n".join(
            f"- {bullet.text} [证据: {', '.join(bullet.evidence_ids)}]"
            for bullet in item.explanation_bullets
        )
        return (
            f"结构化审核说明：\n"
            f"异常类型：{anomalies or '无'}\n"
            f"缺失字段：{missing}\n"
            f"风险等级：{item.risk_level_copy}\n"
            f"建议动作：{item.recommended_action_copy}\n"
            f"说明：\n{bullets}"
        )


class StructuredExplanationService:
    """离线实验入口，解析或校验失败时回退现有确定性模板。"""

    def __init__(self) -> None:
        self.validator = StructuredExplanationValidator()
        self.renderer = StructuredExplanationRenderer()
        self.template_renderer = DeterministicTemplateRenderer()

    def explain(
        self, facts: CanonicalAuditFacts, payload: Any
    ) -> StructuredExplanationResult:
        """执行 schema-first 流程，所有失败均 fail-closed。"""

        try:
            if isinstance(payload, str):
                candidate = StructuredExplanation.model_validate_json(payload)
            else:
                candidate = StructuredExplanation.model_validate(payload)
        except (ValidationError, ValueError, TypeError) as exc:
            validation = StructuredValidationResult(
                passed=False,
                reject_reasons=(f"schema_invalid:{exc.__class__.__name__}",),
            )
            return StructuredExplanationResult(
                status="rejected",
                rendered_text=self.template_renderer.render(facts),
                fallback_used=True,
                validation=validation,
            )
        validation, validated = self.validator.validate(facts, candidate)
        if validated is None:
            return StructuredExplanationResult(
                status="rejected",
                rendered_text=self.template_renderer.render(facts),
                fallback_used=True,
                validation=validation,
            )
        return StructuredExplanationResult(
            status="accepted",
            rendered_text=self.renderer.render(facts, validated),
            fallback_used=False,
            validation=validation,
        )


def build_rule_only_structured_explanation(
    facts: CanonicalAuditFacts,
) -> StructuredExplanation:
    """直接复制确定性事实，建立不训练模型的 rule-only baseline。"""

    bullets: list[StructuredExplanationBullet] = []
    for anomaly in facts.anomaly_types:
        evidence_id = f"anomaly.{anomaly.value}"
        bullets.append(
            StructuredExplanationBullet(
                text=f"检测到{ANOMALY_LABELS[anomaly]}。",
                evidence_ids=(evidence_id,),
            )
        )
    for field in facts.missing_fields:
        evidence_id = f"missing.{field}"
        bullets.append(
            StructuredExplanationBullet(
                text=f"{_field_label(field)}未提供（缺失）。",
                evidence_ids=(evidence_id,),
            )
        )
    cited = tuple(
        dict.fromkeys(
            evidence_id for bullet in bullets for evidence_id in bullet.evidence_ids
        )
    )
    return StructuredExplanation(
        anomaly_types=facts.anomaly_types,
        missing_fields=facts.missing_fields,
        cited_evidence_ids=cited,
        risk_level_copy=facts.risk_level,
        recommended_action_copy=facts.recommended_action,
        explanation_bullets=tuple(bullets),
    )


def summarize_reject_reasons(
    results: list[StructuredExplanationResult],
) -> dict[str, int]:
    """汇总拒绝原因，供 debug report 使用。"""

    counts = Counter(
        reason
        for result in results
        for reason in result.validation.reject_reasons
    )
    return dict(sorted(counts.items()))


def _field_label(field: str) -> str:
    """把固定字段名转换成稳定中文标签。"""

    return {
        "po_number": "采购订单号",
        "grn_number": "收货单号",
        "invoice_number": "发票号",
        "vendor_name": "供应商",
        "total_amount": "金额",
    }.get(field, field)
