"""发票状态流约束。"""

from procureguard.models.status import InvoiceStatus

ALLOWED_INVOICE_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.PENDING: {InvoiceStatus.PROCESSING, InvoiceStatus.REJECTED},
    InvoiceStatus.PROCESSING: {
        InvoiceStatus.APPROVED,
        InvoiceStatus.REJECTED,
        InvoiceStatus.REVIEW,
    },
    InvoiceStatus.REVIEW: {InvoiceStatus.APPROVED, InvoiceStatus.REJECTED},
    InvoiceStatus.APPROVED: set(),
    InvoiceStatus.REJECTED: set(),
}


class InvalidInvoiceStatusTransition(ValueError):
    """发票状态非法流转错误。"""


def can_transition_invoice(
    current: InvoiceStatus | str,
    target: InvoiceStatus | str,
) -> bool:
    """判断发票状态是否允许流转。"""

    current_status = InvoiceStatus(current)
    target_status = InvoiceStatus(target)
    return target_status in ALLOWED_INVOICE_TRANSITIONS[current_status]


def validate_invoice_transition(
    current: InvoiceStatus | str,
    target: InvoiceStatus | str,
) -> None:
    """校验发票状态流转，非法时抛出明确错误。"""

    current_status = InvoiceStatus(current)
    target_status = InvoiceStatus(target)
    if not can_transition_invoice(current_status, target_status):
        raise InvalidInvoiceStatusTransition(
            f"Invalid invoice status transition: {current_status.value} -> {target_status.value}"
        )
