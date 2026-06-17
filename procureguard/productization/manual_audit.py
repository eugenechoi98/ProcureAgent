"""把手动字段和显式 mock 上下文接入现有确定性审核链。"""

from __future__ import annotations

from datetime import date
import sqlite3
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from procureguard.db import initialize_database, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.db.json_utils import dumps_json
from procureguard.models.audit import AuditReport
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.repositories import InvoiceRepository
from procureguard.services import AgentInvoiceProcessor


class ManualLineItem(BaseModel):
    """手动输入的发票或 PO 行项目。"""

    model_config = ConfigDict(extra="forbid")
    item: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, ge=0)

    @field_validator("item")
    @classmethod
    def normalize_item(cls, value: str) -> str:
        """拒绝只有空白的项目名称。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("item must not be blank")
        return normalized


class ReceivedLineItem(BaseModel):
    """显式 mock GRN 的已收货数量。"""

    model_config = ConfigDict(extra="forbid")
    item: str = Field(min_length=1)
    received_quantity: float = Field(ge=0)

    @field_validator("item")
    @classmethod
    def normalize_item(cls, value: str) -> str:
        """拒绝只有空白的项目名称。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("item must not be blank")
        return normalized


class ManualInvoiceFields(BaseModel):
    """用户直接填写的发票字段，不代表模型抽取结果。"""

    model_config = ConfigDict(extra="forbid")
    invoice_number: str = Field(min_length=1)
    vendor_name: str = Field(min_length=1)
    invoice_date: date
    total_amount: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    po_number: str = Field(min_length=1)
    line_items: list[ManualLineItem] = Field(min_length=1)

    @field_validator("invoice_number", "vendor_name", "po_number")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """清理必填文本并拒绝空白值。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("required text field must not be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """要求三位英文字母货币代码。"""

        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha() or not normalized.isascii():
            raise ValueError("currency must be a three-letter ASCII code")
        return normalized


class ExplicitMockProcurementContext(BaseModel):
    """仅对本次请求生效的显式 mock 采购上下文。"""

    model_config = ConfigDict(extra="forbid")
    po_number: str = Field(min_length=1)
    po_vendor_name: str = Field(min_length=1)
    po_total_amount: float = Field(ge=0)
    po_currency: str = Field(min_length=3, max_length=3)
    po_status: Literal["open", "closed", "cancelled"] = "open"
    po_line_items: list[ManualLineItem] = Field(min_length=1)
    grn_available: bool
    grn_number: str | None = None
    grn_received_date: date | None = None
    grn_line_items: list[ReceivedLineItem] = Field(default_factory=list)
    duplicate_invoice_exists: bool = False
    policy_profile: Literal["mock_default"] = "mock_default"

    @field_validator("po_number", "po_vendor_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """清理显式 mock PO 的必填文本。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("required context field must not be blank")
        return normalized

    @field_validator("po_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """要求三位英文字母货币代码。"""

        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha() or not normalized.isascii():
            raise ValueError("po_currency must be a three-letter ASCII code")
        return normalized

    @model_validator(mode="after")
    def validate_grn_fields(self) -> "ExplicitMockProcurementContext":
        """让 GRN 可用性与字段组合保持一致。"""

        if self.grn_available:
            if not self.grn_number or not self.grn_number.strip():
                raise ValueError("grn_number is required when grn_available is true")
            if self.grn_received_date is None:
                raise ValueError("grn_received_date is required when grn_available is true")
            if not self.grn_line_items:
                raise ValueError("grn_line_items are required when grn_available is true")
            self.grn_number = self.grn_number.strip()
        elif self.grn_number or self.grn_received_date or self.grn_line_items:
            raise ValueError("GRN details must be empty when grn_available is false")
        return self


class ManualAuditMetadata(BaseModel):
    """固定输入来源和可选用户备注。"""

    model_config = ConfigDict(extra="forbid")
    source: Literal["manual_input"] = "manual_input"
    context_source: Literal["explicit_mock_context"] = "explicit_mock_context"
    explanation_mode: Literal["template"] = "template"
    user_note: str | None = Field(default=None, max_length=500)


class ManualAuditRequest(BaseModel):
    """Phase 4C 手动审核请求。"""

    model_config = ConfigDict(extra="forbid")
    invoice_fields: ManualInvoiceFields
    procurement_context: ExplicitMockProcurementContext
    metadata: ManualAuditMetadata = Field(default_factory=ManualAuditMetadata)


class SourceLabels(BaseModel):
    """向用户明确每类结果的真实来源。"""

    invoice_field_source: Literal["manual_input"] = "manual_input"
    procurement_context_source: Literal["explicit_mock_context"] = "explicit_mock_context"
    risk_decision_source: Literal["deterministic_rules"] = "deterministic_rules"
    explanation_source: Literal["deterministic_template"] = "deterministic_template"
    live_layoutlmv3_used: Literal[False] = False
    live_lora_used: Literal[False] = False
    payment_authority: Literal[False] = False


class FallbackStatus(BaseModel):
    """区分模板默认路径与真正的模型 fallback。"""

    used: bool = False
    reason: str | None = None


class ManualAuditResponse(BaseModel):
    """手动审核结果和产品边界标签。"""

    audit_id: str
    trace_id: str
    audit_report: AuditReport
    risk_level: str
    recommended_action: str
    source_labels: SourceLabels = Field(default_factory=SourceLabels)
    fallback_status: FallbackStatus = Field(default_factory=FallbackStatus)
    explanation_mode_used: Literal["template"] = "template"
    warnings: list[str]


def run_manual_audit(request: ManualAuditRequest) -> ManualAuditResponse:
    """在请求级内存数据库中复用现有 Phase 2 审核主链。"""

    audit_id = f"manual_{uuid4().hex}"
    conn = get_connection(":memory:")
    try:
        initialize_database(conn)
        seed_policy_documents(conn)
        _insert_explicit_context(conn, request)
        InvoiceRepository(conn).create_invoice(
            invoice_id=audit_id,
            file_path="manual_input/no_uploaded_file",
            file_hash=f"manual-input-{audit_id}",
        )
        report = AgentInvoiceProcessor(conn, explanation_mode="template").process_extracted_invoice(
            audit_id,
            _to_extracted_fields(request.invoice_fields),
        )
    finally:
        conn.close()

    return ManualAuditResponse(
        audit_id=audit_id,
        trace_id=report.trace_id,
        audit_report=report,
        risk_level=report.risk_level.value,
        recommended_action=report.recommended_action.value,
        warnings=[
            "Manual invoice fields were not extracted from an uploaded image.",
            "PO and GRN data are explicit mock context, not enterprise system records.",
            "This MVP has no durable persistence; the API may retain it in process memory until restart.",
            "This research prototype is not financial advice or payment authority.",
        ],
    )


def _to_extracted_fields(fields: ManualInvoiceFields) -> ExtractedFields:
    """把产品输入适配为现有 ExtractedFields，不修改共享契约。"""

    return ExtractedFields(
        vendor_name=fields.vendor_name,
        invoice_number=fields.invoice_number,
        invoice_date=fields.invoice_date.isoformat(),
        po_number=fields.po_number,
        total_amount=fields.total_amount,
        currency=fields.currency,
        line_items=[
            LineItem(item=item.item, qty=item.quantity, unit_price=item.unit_price, amount=item.amount)
            for item in fields.line_items
        ],
        extraction_confidence=1.0,
        extraction_model="manual_input",
    )


def _insert_explicit_context(conn: sqlite3.Connection, request: ManualAuditRequest) -> None:
    """只向本次内存数据库写入用户显式 mock 上下文。"""

    context = request.procurement_context
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
                {"item": item.item, "qty": item.quantity, "unit_price": item.unit_price, "amount": item.amount}
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
        fields = request.invoice_fields
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
