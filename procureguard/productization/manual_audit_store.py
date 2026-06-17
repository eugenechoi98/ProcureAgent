"""本地 MVP 的进程内审核结果、导出和人工复核存储。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from procureguard.productization.manual_audit import ManualAuditRequest, ManualAuditResponse


BOUNDARY_NOTICE = (
    "Research/demo audit only. This export is not a financial payment instrument, "
    "compliance approval, or enterprise procurement record."
)


class ManualReviewDecisionRequest(BaseModel):
    """本地 MVP 人工复核输入。"""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject", "request_more_info"]
    reviewer_note: str = Field(min_length=1, max_length=1000)

    @field_validator("reviewer_note")
    @classmethod
    def normalize_reviewer_note(cls, value: str) -> str:
        """拒绝只有空白的 reviewer note。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("reviewer_note must not be blank")
        return normalized


class ManualReviewMetadata(BaseModel):
    """与确定性规则结果分离的人工复核元数据。"""

    review_status: Literal["not_required", "pending", "resolved"]
    review_decision: Literal["approve", "reject", "request_more_info"] | None = None
    reviewer_note: str | None = None
    reviewed_at: str | None = None
    decision_authority: Literal[False] = False


class ManualAuditRecord(BaseModel):
    """进程内保存的完整手动审核记录。"""

    request: ManualAuditRequest
    response: ManualAuditResponse
    created_at: str
    review: ManualReviewMetadata


class ManualAuditExport(BaseModel):
    """稳定且机器可读的 AuditReport 导出契约。"""

    export_version: Literal["phase4d-v1"] = "phase4d-v1"
    generated_at: str
    boundary_notice: str = BOUNDARY_NOTICE
    payment_authority: Literal[False] = False
    audit_id: str
    trace_id: str
    invoice_fields: dict
    procurement_context_summary: dict
    risk_level: str
    recommended_action: str
    validation_results: dict
    anomaly_explanation: str
    explanation_text: str
    source_labels: dict
    fallback_status: dict
    explanation_mode_used: str
    warnings: list[str]
    review_status: str
    review_decision: str | None
    reviewer_note: str | None
    reviewed_at: str | None
    deterministic_result_unchanged: Literal[True] = True


class ManualAuditStore:
    """保存当前 API 进程中的本地 MVP 审核状态。"""

    def __init__(self) -> None:
        self._records: dict[str, ManualAuditRecord] = {}
        self._lock = RLock()

    def save(self, request: ManualAuditRequest, response: ManualAuditResponse) -> ManualAuditRecord:
        """保存一次审核并初始化 review 状态。"""

        review_status = (
            "pending"
            if response.recommended_action == "request_human_approval"
            or response.risk_level in {"medium", "high"}
            else "not_required"
        )
        record = ManualAuditRecord(
            request=request,
            response=response,
            created_at=_now_iso(),
            review=ManualReviewMetadata(review_status=review_status),
        )
        with self._lock:
            self._records[response.audit_id] = record
        return record.model_copy(deep=True)

    def get(self, audit_id: str) -> ManualAuditRecord | None:
        """读取记录快照，避免调用方修改 store。"""

        with self._lock:
            record = self._records.get(audit_id)
            return record.model_copy(deep=True) if record else None

    def review_queue(self) -> list[ManualAuditRecord]:
        """返回仍待人工复核的 medium/high 记录。"""

        with self._lock:
            records = [
                record.model_copy(deep=True)
                for record in self._records.values()
                if record.review.review_status == "pending"
            ]
        return sorted(records, key=lambda item: (item.created_at, item.response.audit_id))

    def submit_review(
        self,
        audit_id: str,
        decision: ManualReviewDecisionRequest,
    ) -> ManualAuditRecord:
        """附加人工决定，不修改原始风险与建议动作。"""

        with self._lock:
            record = self._records.get(audit_id)
            if record is None:
                raise LookupError(f"Manual audit {audit_id} was not found.")
            if record.review.review_status == "not_required":
                raise ValueError(f"Manual audit {audit_id} does not require human review.")
            if record.review.review_status == "resolved":
                raise RuntimeError(f"Manual audit {audit_id} has already been reviewed.")
            record.review = ManualReviewMetadata(
                review_status="resolved",
                review_decision=decision.decision,
                reviewer_note=decision.reviewer_note,
                reviewed_at=_now_iso(),
            )
            return record.model_copy(deep=True)

    def clear(self) -> None:
        """清空当前进程中的 manual audit MVP 数据。"""

        with self._lock:
            self._records.clear()


def build_export(record: ManualAuditRecord) -> ManualAuditExport:
    """把保存记录转换成稳定导出契约。"""

    report = record.response.audit_report
    explanation = report.explanation
    return ManualAuditExport(
        generated_at=_now_iso(),
        audit_id=record.response.audit_id,
        trace_id=record.response.trace_id,
        invoice_fields=record.request.invoice_fields.model_dump(mode="json"),
        procurement_context_summary=_context_summary(record.request),
        risk_level=record.response.risk_level,
        recommended_action=record.response.recommended_action,
        validation_results={
            "po_match": report.po_match,
            "goods_receipt_match": report.goods_receipt_match,
            "policy_flags": report.policy_flags,
            "evidence": [item.model_dump(mode="json") for item in report.evidence],
        },
        anomaly_explanation=report.anomaly_explanation,
        explanation_text=explanation.explanation_text if explanation else report.anomaly_explanation,
        source_labels=record.response.source_labels.model_dump(mode="json"),
        fallback_status=record.response.fallback_status.model_dump(mode="json"),
        explanation_mode_used=record.response.explanation_mode_used,
        warnings=record.response.warnings,
        review_status=record.review.review_status,
        review_decision=record.review.review_decision,
        reviewer_note=record.review.reviewer_note,
        reviewed_at=record.review.reviewed_at,
    )


def render_export_json(record: ManualAuditRecord) -> str:
    """渲染稳定 UTF-8 JSON。"""

    payload = build_export(record).model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_export_markdown(record: ManualAuditRecord) -> str:
    """渲染适合复制和审计说明的 Markdown。"""

    export = build_export(record)
    invoice = export.invoice_fields
    context = export.procurement_context_summary
    labels = export.source_labels
    validation = export.validation_results
    evidence = validation["evidence"]
    evidence_lines = [
        f"- `{item['field']}`: invoice=`{item['invoice_value']}`, expected=`{item['expected_value']}`, received=`{item['received_value']}`"
        for item in evidence
    ] or ["- None"]
    warnings = [f"- {item}" for item in export.warnings]
    return "\n".join(
        [
            "# ProcureGuard Manual Audit Export",
            "",
            f"> **Boundary notice:** {export.boundary_notice}",
            "",
            "## Audit Metadata",
            "",
            f"- Audit ID: `{export.audit_id}`",
            f"- Trace ID: `{export.trace_id}`",
            f"- Generated at: `{export.generated_at}`",
            f"- Payment authority: `{str(export.payment_authority).lower()}`",
            "",
            "## Invoice Fields",
            "",
            f"- Invoice number: `{invoice['invoice_number']}`",
            f"- Vendor: `{invoice['vendor_name']}`",
            f"- Invoice date: `{invoice['invoice_date']}`",
            f"- Total: `{invoice['currency']} {invoice['total_amount']}`",
            f"- PO number: `{invoice['po_number']}`",
            "",
            "## Explicit Mock Procurement Context",
            "",
            f"- PO: `{context['po_number']}` / `{context['po_currency']} {context['po_total_amount']}`",
            f"- PO vendor: `{context['po_vendor_name']}`",
            f"- GRN available: `{str(context['grn_available']).lower()}`",
            f"- GRN number: `{context['grn_number']}`",
            f"- Duplicate fixture: `{str(context['duplicate_invoice_exists']).lower()}`",
            "",
            "## Deterministic Audit Result",
            "",
            f"- Risk level: `{export.risk_level}`",
            f"- Recommended action: `{export.recommended_action}`",
            f"- PO match: `{str(validation['po_match']).lower()}`",
            f"- Goods receipt match: `{str(validation['goods_receipt_match']).lower()}`",
            f"- Policy flags: `{', '.join(validation['policy_flags']) or 'none'}`",
            "",
            "### Evidence",
            "",
            *evidence_lines,
            "",
            "### Explanation",
            "",
            export.explanation_text,
            "",
            "## Source And Fallback Status",
            "",
            f"- Invoice field source: `{labels['invoice_field_source']}`",
            f"- Procurement context source: `{labels['procurement_context_source']}`",
            f"- Risk decision source: `{labels['risk_decision_source']}`",
            f"- Explanation source: `{labels['explanation_source']}`",
            f"- Live LayoutLMv3 used: `{str(labels['live_layoutlmv3_used']).lower()}`",
            f"- Live LoRA used: `{str(labels['live_lora_used']).lower()}`",
            f"- Fallback used: `{str(export.fallback_status['used']).lower()}`",
            f"- Fallback reason: `{export.fallback_status['reason']}`",
            f"- Explanation mode: `{export.explanation_mode_used}`",
            "",
            "## Human Review",
            "",
            f"- Review status: `{export.review_status}`",
            f"- Review decision: `{export.review_decision}`",
            f"- Reviewer note: `{export.reviewer_note}`",
            f"- Reviewed at: `{export.reviewed_at}`",
            f"- Deterministic result unchanged: `{str(export.deterministic_result_unchanged).lower()}`",
            "",
            "## Warnings",
            "",
            *warnings,
            "",
        ]
    )


def _context_summary(request: ManualAuditRequest) -> dict:
    """导出显式 mock 上下文摘要，不称其为企业数据。"""

    context = request.procurement_context
    return {
        "context_source": request.metadata.context_source,
        "po_number": context.po_number,
        "po_vendor_name": context.po_vendor_name,
        "po_total_amount": context.po_total_amount,
        "po_currency": context.po_currency,
        "po_status": context.po_status,
        "grn_available": context.grn_available,
        "grn_number": context.grn_number,
        "grn_received_date": context.grn_received_date.isoformat() if context.grn_received_date else None,
        "duplicate_invoice_exists": context.duplicate_invoice_exists,
        "policy_profile": context.policy_profile,
    }


def _now_iso() -> str:
    """生成稳定 UTC 时间文本。"""

    return datetime.now(timezone.utc).isoformat()
