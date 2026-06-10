"""状态流和枚举定义。"""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """发票处理状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEW = "review"


class RiskLevel(StrEnum):
    """审核风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendedAction(StrEnum):
    """审计报告建议动作。"""

    AUTO_APPROVE = "auto_approve"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"
    REJECT = "reject"


class ReviewStatus(StrEnum):
    """人工审核队列状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
