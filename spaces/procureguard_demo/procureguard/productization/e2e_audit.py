"""Phase 4G-EXT 端到端审核编排入口。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Literal
import warnings
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from procureguard.db import initialize_database, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.db.json_utils import dumps_json
from procureguard.models.audit import AuditReport
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.phase3.explanation.orchestrator import ExplanationMode, RewriteProvider
from procureguard.productization.demo_seed import (
    MOCK_DATA_NOTICE,
    resolve_demo_procurement_context,
)
from procureguard.productization.field_confirmation import (
    ConfirmedAuditInput,
    FieldCandidate,
    FieldConfirmationRequest,
    FieldDecision,
    confirm_fields,
    confirmed_audit_input_to_extracted_fields,
)
from procureguard.productization.manual_audit import ExplicitMockProcurementContext
from procureguard.repositories import InvoiceRepository
from procureguard.services import AgentInvoiceProcessor


warnings.filterwarnings(
    "ignore",
    message='Field name "json" in "ExecuteAuditResponse" shadows an attribute in parent "BaseModel"',
    category=UserWarning,
)


class ExecuteAuditRequest(BaseModel):
    """端到端 MVP 审核请求。"""

    model_config = ConfigDict(extra="forbid")
    image: str | None = None
    field_candidates: list[FieldCandidate] | None = None
    confirmation_decisions: list[FieldDecision] = Field(default_factory=list)
    confirmed_fields: ExtractedFields | None = None
    procurement_context: ExplicitMockProcurementContext | None = None
    confirmation_mode: Literal["human", "simulated_human"] = "human"
    explanation_mode: ExplanationMode = "template"

    @model_validator(mode="after")
    def require_one_input_source(self) -> "ExecuteAuditRequest":
        """至少提供 image、candidate 或 confirmed_fields 之一。"""

        if not self.image and not self.field_candidates and self.confirmed_fields is None:
            raise ValueError("image, field_candidates, or confirmed_fields is required")
        if self.confirmed_fields is None and not self.confirmation_decisions:
            raise ValueError("confirmation_decisions are required before Phase 2")
        return self


class PipelineTrace(BaseModel):
    """端到端执行轨迹。"""

    ocr_used: bool
    layoutlmv3_used: bool
    fields_confirmed_by: Literal["human", "simulated_human", "provided_confirmed_fields"]
    fields_modified: list[str]
    rejected_fields: list[str]
    missing_fields: list[str]
    phase2_decision_source: Literal["deterministic_rules"]
    risk_level_origin: Literal["rules_only"]
    recommended_action_origin: Literal["rules_only"]
    lora_used_for_audit: Literal[False] = False
    guard_status: Literal["not_used", "passed", "failed_fallback"] = "not_used"
    explanation_source: str = "deterministic_template"
    explanation_mode_requested: str = "template"
    explanation_mode_used: str = "template"
    fallback_reason: str | None = None
    procurement_context_source: Literal[
        "explicit_mock_context", "pre_seeded_mock_po_grn", "no_po_found"
    ] = "explicit_mock_context"
    demo_mode: bool = False
    mock_data_notice: str | None = None


class ExecuteSourceLabels(BaseModel):
    """端到端响应的来源边界标签。"""

    demo_mode: bool = False
    context_source: Literal[
        "explicit_mock_context", "pre_seeded_mock_po_grn", "no_po_found"
    ] = "explicit_mock_context"
    payment_authority: Literal[False] = False
    live_layoutlmv3_used: bool = False
    live_lora_used: bool = False
    risk_decision_source: Literal["deterministic_rules"] = "deterministic_rules"
    mock_data_notice: str | None = None


class ExecuteAuditResponse(BaseModel):
    """统一端到端审核输出。"""

    audit_id: str
    json: dict[str, Any]
    markdown: str
    trace: PipelineTrace
    source_labels: ExecuteSourceLabels
    payment_authority: Literal[False] = False


ImageCandidateRunner = Callable[[str], tuple[list[FieldCandidate], dict[str, Any]]]


def execute_audit_pipeline(
    request: ExecuteAuditRequest,
    *,
    database_path: str | Path | None = None,
    image_candidate_runner: ImageCandidateRunner | None = None,
    explanation_rewrite_provider: RewriteProvider | None = None,
    demo_mode: bool | None = None,
) -> ExecuteAuditResponse:
    """串联 image/candidates/confirmed_fields 到 Phase 2 AuditReport。"""

    audit_id = f"e2e_{uuid4().hex}"
    ocr_used = False
    layoutlmv3_used = False
    candidates = request.field_candidates or []
    image_trace: dict[str, Any] = {}
    if request.image:
        runner = image_candidate_runner or _run_image_to_candidates
        candidates, image_trace = runner(request.image)
        ocr_used = True
        layoutlmv3_used = True
    elif candidates:
        layoutlmv3_used = True

    if request.confirmed_fields is not None:
        extracted = _mark_confirmed_fields(request.confirmed_fields)
        corrected_fields: dict[str, Any] = {}
        rejected_fields: list[str] = []
        missing_fields: list[str] = []
        fields_confirmed_by: Literal["human", "simulated_human", "provided_confirmed_fields"] = (
            "provided_confirmed_fields"
        )
    else:
        confirmation = confirm_fields(
            FieldConfirmationRequest(
                candidates=candidates,
                decisions=request.confirmation_decisions,
                confirmation_mode=request.confirmation_mode,
                trace_id=audit_id,
            )
        )
        if confirmation.audit_input is None:
            raise ValueError(f"Confirmed fields are incomplete: {confirmation.missing_fields}")
        extracted = confirmed_audit_input_to_extracted_fields(confirmation.audit_input)
        corrected_fields = confirmation.corrected_fields
        rejected_fields = confirmation.rejected_fields
        missing_fields = confirmation.missing_fields
        fields_confirmed_by = request.confirmation_mode

    context = request.procurement_context
    context_source: Literal[
        "explicit_mock_context", "pre_seeded_mock_po_grn", "no_po_found"
    ] = "explicit_mock_context"
    if context is None:
        if database_path is None:
            raise ValueError("database_path is required when procurement_context is omitted")
        context, context_source = resolve_demo_procurement_context(database_path, extracted)
        if context is not None:
            extracted = extracted.model_copy(
                update={
                    "po_number": context.po_number,
                    "currency": context.po_currency,
                    "line_items": _ensure_demo_line_items(extracted, context),
                }
            )
        else:
            extracted = extracted.model_copy(
                update={
                    "po_number": extracted.po_number or "NO-PO-FOUND",
                    "line_items": _ensure_fallback_line_items(extracted),
                }
            )
    effective_demo_mode = bool(demo_mode) or context_source in {
        "pre_seeded_mock_po_grn",
        "no_po_found",
    }

    report = _run_phase2(
        audit_id,
        extracted,
        context,
        explanation_mode=request.explanation_mode,
        explanation_rewrite_provider=explanation_rewrite_provider,
    )
    guard_status: Literal["not_used", "passed", "failed_fallback"] = "not_used"
    explanation_source = "deterministic_template"
    if report.explanation and report.explanation.explanation_mode in {
        "shadow",
        "experimental",
        "shadow_lora",
        "guarded_lora",
    }:
        guard_status = (
            "failed_fallback"
            if report.explanation.fallback_reason
            else "passed"
        )
        explanation_source = report.explanation.final_source
    trace = PipelineTrace(
        ocr_used=ocr_used,
        layoutlmv3_used=layoutlmv3_used,
        fields_confirmed_by=fields_confirmed_by,
        fields_modified=sorted(corrected_fields),
        rejected_fields=rejected_fields,
        missing_fields=missing_fields,
        phase2_decision_source="deterministic_rules",
        risk_level_origin="rules_only",
        recommended_action_origin="rules_only",
        guard_status=guard_status,
        explanation_source=explanation_source,
        explanation_mode_requested=request.explanation_mode,
        explanation_mode_used=(
            report.explanation.explanation_mode_used
            if report.explanation
            else request.explanation_mode
        ),
        fallback_reason=report.explanation.fallback_reason
        if report.explanation
        else None,
        procurement_context_source=context_source,
        demo_mode=effective_demo_mode,
        mock_data_notice=MOCK_DATA_NOTICE if effective_demo_mode else None,
    )
    source_labels = ExecuteSourceLabels(
        demo_mode=effective_demo_mode,
        context_source=context_source,
        live_layoutlmv3_used=layoutlmv3_used,
        live_lora_used=bool(report.explanation and report.explanation.used_rewrite),
        mock_data_notice=MOCK_DATA_NOTICE if effective_demo_mode else None,
    )
    audit_report_json = report.model_dump(mode="json")
    audit_report_json["source_labels"] = source_labels.model_dump(mode="json")
    audit_report_json["mismatches"] = _mismatches_from_evidence(audit_report_json["evidence"])
    if context_source == "pre_seeded_mock_po_grn" and any(
        item["field"] == "total_amount" for item in audit_report_json["mismatches"]
    ):
        audit_report_json["po_match"] = False
    if context_source == "no_po_found":
        audit_report_json["context_resolution"] = {
            "status": "no_po_found",
            "message": "No pre-seeded demo PO/GRN matched the confirmed invoice fields.",
        }
    payload = {
        "audit_id": audit_id,
        "audit_report": audit_report_json,
        "trace": trace.model_dump(mode="json"),
        "image_trace": image_trace,
        "source_labels": source_labels.model_dump(mode="json"),
        "context_source": "demo_mock_database" if effective_demo_mode else context_source,
        "demo_mode": effective_demo_mode,
        "mock_data_notice": MOCK_DATA_NOTICE if effective_demo_mode else None,
        "exports": {"json_version": "phase4g-ext-v1", "markdown_version": "phase4g-ext-v1"},
    }
    return ExecuteAuditResponse(
        audit_id=audit_id,
        json=payload,
        markdown=_render_markdown(report, trace, source_labels),
        trace=trace,
        source_labels=source_labels,
    )


def _run_image_to_candidates(image_path: str) -> tuple[list[FieldCandidate], dict[str, Any]]:
    """运行 Phase 4F 本地 image -> LayoutLMv3 candidates。"""

    from procureguard.extraction.live_spike import run_live_extraction

    output_dir = Path(".tmp") / "phase4g_ext" / uuid4().hex
    result = run_live_extraction(image_path, output_dir)
    payload = json.loads((output_dir / "layoutlmv3_field_candidates.json").read_text(encoding="utf-8"))
    candidates = [FieldCandidate.model_validate(item) for item in payload["fields"]]
    return candidates, {"output_dir": str(output_dir), **result}


def _run_phase2(
    audit_id: str,
    fields: ExtractedFields,
    context: ExplicitMockProcurementContext | None,
    *,
    explanation_mode: ExplanationMode,
    explanation_rewrite_provider: RewriteProvider | None,
) -> AuditReport:
    """只用 confirmed ExtractedFields 调用 Phase 2 确定性审核。"""

    conn = get_connection(":memory:")
    try:
        initialize_database(conn)
        seed_policy_documents(conn)
        if context is not None:
            _insert_context(conn, context, fields)
        InvoiceRepository(conn).create_invoice(
            invoice_id=audit_id,
            file_path="confirmed_fields/no_raw_model_bypass",
            file_hash=f"confirmed-fields-{audit_id}",
        )
        return AgentInvoiceProcessor(
            conn,
            explanation_mode=explanation_mode,
            explanation_rewrite_provider=explanation_rewrite_provider,
        ).process_extracted_invoice(audit_id, fields)
    finally:
        conn.close()


def _insert_context(
    conn: sqlite3.Connection,
    context: ExplicitMockProcurementContext,
    fields: ExtractedFields,
) -> None:
    """写入本次请求显式 mock PO/GRN 上下文。"""

    conn.execute(
        """INSERT INTO purchase_orders
        (po_number, vendor_name, total_amount, currency, line_items_json, created_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            context.po_number,
            context.po_vendor_name,
            context.po_total_amount,
            context.po_currency,
            dumps_json([
                {
                    "item": item.item,
                    "qty": item.quantity,
                    "unit_price": item.unit_price,
                    "amount": item.amount,
                }
                for item in context.po_line_items
            ]),
            None,
            context.po_status,
        ),
    )
    if context.grn_available:
        conn.execute(
            """INSERT INTO goods_receipts
            (grn_number, po_number, received_date, line_items_json, receiver)
            VALUES (?, ?, ?, ?, ?)""",
            (
                context.grn_number,
                context.po_number,
                context.grn_received_date.isoformat(),
                dumps_json([
                    {"item": item.item, "received_qty": item.received_quantity}
                    for item in context.grn_line_items
                ]),
                "explicit.mock.context",
            ),
        )
    if context.duplicate_invoice_exists:
        conn.execute(
            """INSERT INTO invoices
            (id, file_path, file_hash, upload_time, status, extracted_fields_json)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                f"duplicate_fixture_{uuid4().hex}",
                "explicit_mock_context/duplicate.json",
                f"duplicate-context-{uuid4().hex}",
                0,
                "approved",
                dumps_json({"invoice_number": fields.invoice_number, "vendor_name": fields.vendor_name}),
            ),
        )
    conn.commit()


def _mark_confirmed_fields(fields: ExtractedFields) -> ExtractedFields:
    """把外部传入字段标记为确认事实，避免保留 raw model 来源。"""

    return fields.model_copy(
        update={
            "extraction_confidence": 1.0,
            "extraction_model": "provided_confirmed_fields",
        }
    )


def _ensure_demo_line_items(
    fields: ExtractedFields,
    context: ExplicitMockProcurementContext,
) -> list:
    """演示字段无行项目时补齐 Receipt total，保证 GRN 数量匹配可运行。"""

    if fields.line_items:
        return fields.line_items
    return [
        LineItem(
            item="Receipt total",
            qty=1,
            unit_price=fields.total_amount or context.po_total_amount,
            amount=fields.total_amount or context.po_total_amount,
        )
    ]


def _ensure_fallback_line_items(fields: ExtractedFields) -> list:
    """未找到 PO 时也给 Phase 2 一个稳定的占位行项目。"""

    if fields.line_items:
        return fields.line_items
    return [
        LineItem(
            item="Receipt total",
            qty=1,
            unit_price=fields.total_amount or 0,
            amount=fields.total_amount or 0,
        )
    ]


def _mismatches_from_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为 demo response 提供更贴近用户预期的 mismatch 字段。"""

    mismatches: list[dict[str, Any]] = []
    for item in evidence:
        mismatch = {
            "field": item.get("field"),
            "invoice_value": item.get("invoice_value"),
        }
        if item.get("received_value") is not None:
            mismatch["received"] = item.get("received_value")
        if item.get("expected_value") is not None:
            mismatch["expected"] = item.get("expected_value")
        mismatches.append(mismatch)
    return mismatches


def _render_markdown(
    report: AuditReport,
    trace: PipelineTrace,
    source_labels: ExecuteSourceLabels,
) -> str:
    """渲染端到端 Markdown AuditReport。"""

    explanation = report.explanation.explanation_text if report.explanation else report.anomaly_explanation
    return "\n".join(
        [
            "# ProcureGuard End-to-End Audit Report",
            "",
            f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
            "- Payment authority: `false`",
            f"- Demo mode: `{str(source_labels.demo_mode).lower()}`",
            f"- Context source: `{source_labels.context_source}`",
            "",
            "## Deterministic Audit Result",
            "",
            f"- Risk level: `{report.risk_level.value}`",
            f"- Recommended action: `{report.recommended_action.value}`",
            f"- PO match: `{str(report.po_match).lower()}`",
            f"- Goods receipt match: `{str(report.goods_receipt_match).lower()}`",
            f"- Policy flags: `{', '.join(report.policy_flags) or 'none'}`",
            "",
            "## Explanation",
            "",
            explanation,
            "",
            "## Trace",
            "",
            f"- OCR used: `{str(trace.ocr_used).lower()}`",
            f"- LayoutLMv3 used: `{str(trace.layoutlmv3_used).lower()}`",
            f"- Fields confirmed by: `{trace.fields_confirmed_by}`",
            f"- Fields modified: `{', '.join(trace.fields_modified) or 'none'}`",
            f"- Phase 2 decision source: `{trace.phase2_decision_source}`",
            f"- Risk level origin: `{trace.risk_level_origin}`",
            f"- Recommended action origin: `{trace.recommended_action_origin}`",
            f"- Guard status: `{trace.guard_status}`",
            "",
        ]
    )
