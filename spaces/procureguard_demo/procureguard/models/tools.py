"""5 个 Agent 工具的输入输出契约。"""

from pydantic import BaseModel, Field

from procureguard.models.invoice import GoodsReceipt, PurchaseOrder
from procureguard.models.status import ReviewStatus, RiskLevel


class PurchaseOrderLookupResult(BaseModel):
    """查询采购订单工具返回值。"""

    found: bool
    po_number: str
    purchase_order: PurchaseOrder | None = None
    message: str


class GoodsReceiptLookupResult(BaseModel):
    """查询收货记录工具返回值。"""

    found: bool
    po_number: str
    receipts: list[GoodsReceipt] = Field(default_factory=list)
    message: str


class DuplicateCheckResult(BaseModel):
    """重复发票检查工具返回值。"""

    is_duplicate: bool
    duplicate_check: bool
    invoice_number: str
    vendor_name: str
    matched_invoice_ids: list[str] = Field(default_factory=list)
    message: str


class PolicySearchResult(BaseModel):
    """政策检索结果。"""

    policy_id: str
    section: str
    policy_text: str
    relevance_score: float


class ManualReviewSubmission(BaseModel):
    """提交人工审核工具返回值。"""

    review_id: str
    invoice_id: str
    status: ReviewStatus
    risk_level: RiskLevel
    reason_codes: list[str] = Field(default_factory=list)
