"""后端基础阶段的同步 mock 处理链。"""

import sqlite3

from procureguard.repositories import AuditTraceRepository, InvoiceRepository
from procureguard.models.status import InvoiceStatus, RiskLevel
from procureguard.tools import submit_manual_review


class MockInvoiceProcessor:
    """临时 mock 处理链，只验证接口闭环，不代表真实审核逻辑。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.invoices = InvoiceRepository(conn)
        self.traces = AuditTraceRepository(conn)

    def process(self, invoice_id: str) -> dict[str, str]:
        """同步执行 pending -> processing -> review 的 mock 流程。"""

        self.invoices.update_status(invoice_id, InvoiceStatus.PROCESSING)
        self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="extraction",
            input_data={"mode": "mock"},
            output_data={
                "mode": "mock",
                "message": "OCR and LayoutLMv3 are not executed in backend foundation phase.",
            },
        )
        self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="validation",
            input_data={"mode": "mock"},
            output_data={
                "mode": "mock",
                "reason_codes": ["mock_manual_review_required"],
            },
        )
        self.invoices.update_status(
            invoice_id,
            InvoiceStatus.REVIEW,
            risk_level=RiskLevel.MEDIUM.value,
        )
        submission = submit_manual_review(
            self.conn,
            invoice_id=invoice_id,
            risk_level=RiskLevel.MEDIUM,
            reason_codes=["mock_manual_review_required"],
            evidence=[{"mode": "mock", "step": "backend_foundation"}],
        )
        return {
            "invoice_id": invoice_id,
            "status": InvoiceStatus.REVIEW.value,
            "review_id": submission.review_id,
            "processing_mode": "mock",
        }
