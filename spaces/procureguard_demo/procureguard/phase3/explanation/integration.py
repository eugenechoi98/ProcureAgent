"""Phase 3H 与已完成 Phase 2 审核结果之间的只读适配。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from procureguard.models.audit import EvidenceItem, ExplanationMetadata
from procureguard.models.invoice import ExtractedFields, ValidationResult
from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.orchestrator import (
    ExplanationMode,
    ExplanationResult,
    FallbackOrchestrator,
    RewriteProvider,
)
from procureguard.phase3.schemas import AnomalyType

if TYPE_CHECKING:
    from procureguard.services.risk_engine import RiskAssessment

REASON_CODE_ANOMALIES = {
    "missing_or_invalid_po": AnomalyType.MISSING_PO_NUMBER,
    "amount_discrepancy": AnomalyType.AMOUNT_DISCREPANCY,
    "duplicate_invoice": AnomalyType.DUPLICATE_INVOICE,
    "high_value_approval_required": AnomalyType.HIGH_VALUE_APPROVAL_REQUIRED,
}

MISMATCH_FIELD_ANOMALIES = {
    "quantity": AnomalyType.QUANTITY_MISMATCH,
    "total_amount": AnomalyType.AMOUNT_DISCREPANCY,
    "invoice_number": AnomalyType.DUPLICATE_INVOICE,
    "po_number": AnomalyType.MISSING_PO_NUMBER,
    "vendor_name": AnomalyType.VENDOR_NAME_MISMATCH,
    "grn_number": AnomalyType.MISSING_GOODS_RECEIPT,
}


def build_canonical_audit_facts(
    *,
    invoice_id: str,
    invoice: ExtractedFields,
    validation: ValidationResult,
    assessment: RiskAssessment,
    evidence: Sequence[EvidenceItem],
    policy_flags: Sequence[str],
    grn_number: str | None,
) -> CanonicalAuditFacts:
    """只复制 Phase 2 已确定结果，不重新计算风险或动作。"""

    anomaly_types: list[AnomalyType] = []
    mismatch_fields = {item.field for item in validation.mismatches}
    for item in validation.mismatches:
        anomaly_type = MISMATCH_FIELD_ANOMALIES.get(item.field)
        if anomaly_type is not None:
            anomaly_types.append(anomaly_type)
    for reason_code in assessment.reason_codes:
        anomaly_type = REASON_CODE_ANOMALIES.get(reason_code)
        if anomaly_type is not None:
            anomaly_types.append(anomaly_type)
    if "goods_receipt_mismatch" in assessment.reason_codes:
        anomaly_types.append(
            AnomalyType.QUANTITY_MISMATCH
            if "quantity" in mismatch_fields
            else AnomalyType.MISSING_GOODS_RECEIPT
        )

    missing_fields: list[str] = []
    if invoice.po_number is None:
        missing_fields.append("po_number")
    if (
        "goods_receipt_mismatch" in assessment.reason_codes
        and "quantity" not in mismatch_fields
        and grn_number is None
    ):
        missing_fields.append("grn_number")

    return CanonicalAuditFacts(
        invoice_id=invoice_id,
        vendor_name=invoice.vendor_name,
        invoice_number=invoice.invoice_number,
        po_number=invoice.po_number,
        grn_number=grn_number,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        anomaly_types=tuple(dict.fromkeys(anomaly_types)),
        evidence=tuple(item.model_dump(mode="json") for item in evidence),
        missing_fields=missing_fields,
        risk_level=assessment.risk_level.value,
        recommended_action=assessment.recommended_action.value,
        policy_flags=tuple(policy_flags),
    )


def build_explanation_metadata(
    facts: CanonicalAuditFacts, result: ExplanationResult
) -> ExplanationMetadata:
    """把解释结果转换为 AuditReport 的 additive 输出。"""

    trail = result.audit_trail
    return ExplanationMetadata(
        explanation_text=result.explanation,
        explanation_source=(
            "controlled_rewrite" if result.used_rewrite else "template"
        ),
        explanation_mode=result.mode,
        anomaly_types=[item.value for item in facts.anomaly_types],
        evidence=[
            dict(item) for item in facts.stable_payload()["evidence"]
        ],
        missing_fields=list(facts.missing_fields),
        facts_hash=trail.facts_hash,
        template_version=trail.template_version,
        prompt_version=trail.prompt_version,
        model_version=trail.model_version,
        adapter_version=trail.adapter_version,
        raw_llm_output=trail.raw_llm_output,
        used_rewrite=result.used_rewrite,
        fallback_reason=trail.fallback_reason,
        guard_passed=trail.verifier_result.passed,
        guard_violations=trail.verifier_result.violations,
    )


def generate_guarded_explanation(
    facts: CanonicalAuditFacts,
    *,
    mode: ExplanationMode = "template",
    rewrite_provider: RewriteProvider | None = None,
    orchestrator: FallbackOrchestrator | None = None,
) -> tuple[ExplanationResult, ExplanationMetadata]:
    """执行受控解释并返回完整 trace 与 API 友好元数据。"""

    result = (orchestrator or FallbackOrchestrator()).explain(
        facts,
        mode=mode,
        rewrite_provider=rewrite_provider,
    )
    return result, build_explanation_metadata(facts, result)
