"""发票、采购订单、收货记录和校验结果模型。"""

from typing import Any

from pydantic import BaseModel, Field

from procureguard.models.status import InvoiceStatus, RiskLevel


class LineItem(BaseModel):
    """发票或订单行项目。"""

    item: str
    qty: float
    unit_price: float | None = None
    amount: float | None = None


class MismatchItem(BaseModel):
    """三单匹配发现的不一致项。"""

    field: str
    invoice_value: Any
    expected_value: Any | None = None
    received_value: Any | None = None
    diff: float | None = None
    item: str | None = None


class ExtractedFields(BaseModel):
    """模型抽取后的结构化发票字段。"""

    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    po_number: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total_amount: float | None = None
    currency: str = "USD"
    line_items: list[LineItem] = Field(default_factory=list)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    extraction_model: str


class ValidationResult(BaseModel):
    """确定性规则校验结果。"""

    po_match: bool
    grn_match: bool
    amount_match: bool
    duplicate_check: bool
    mismatches: list[MismatchItem] = Field(default_factory=list)


class PurchaseOrder(BaseModel):
    """采购订单 mock 数据结构。"""

    po_number: str
    vendor_name: str
    total_amount: float
    currency: str = "USD"
    line_items: list[LineItem] = Field(default_factory=list)
    created_date: str | None = None
    status: str = "open"


class GoodsReceipt(BaseModel):
    """收货记录 mock 数据结构。"""

    grn_number: str
    po_number: str
    received_date: str
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    receiver: str | None = None


class InvoiceRecord(BaseModel):
    """数据库中的发票记录。"""

    id: str
    file_path: str
    file_hash: str
    upload_time: int
    status: InvoiceStatus = InvoiceStatus.PENDING
    risk_level: RiskLevel | None = None
    extracted_fields: ExtractedFields | None = None
    validation_result: ValidationResult | None = None
    audit_report: dict[str, Any] | None = None
