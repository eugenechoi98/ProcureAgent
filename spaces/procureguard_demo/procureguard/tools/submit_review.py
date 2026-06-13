"""提交人工审核工具。"""

import sqlite3
import time
from uuid import uuid4

from procureguard.db.json_utils import dumps_json
from procureguard.models.status import ReviewStatus, RiskLevel
from procureguard.models.tools import ManualReviewSubmission


def submit_manual_review(
    conn: sqlite3.Connection,
    invoice_id: str,
    risk_level: RiskLevel | str,
    reason_codes: list[str],
    evidence: list[dict] | None = None,
    assigned_to: str | None = None,
) -> ManualReviewSubmission:
    """把发票放入人工审核队列。"""

    normalized_risk = RiskLevel(risk_level)
    review_id = f"review_{uuid4().hex}"
    conn.execute(
        """
        INSERT INTO review_queue
        (id, invoice_id, risk_level, reason_codes_json, evidence_json, assigned_to, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id,
            invoice_id,
            normalized_risk.value,
            dumps_json(reason_codes),
            dumps_json(evidence or []),
            assigned_to,
            ReviewStatus.PENDING.value,
            int(time.time()),
        ),
    )
    conn.execute(
        "UPDATE invoices SET status = ?, risk_level = ? WHERE id = ?",
        ("review", normalized_risk.value, invoice_id),
    )
    conn.commit()
    return ManualReviewSubmission(
        review_id=review_id,
        invoice_id=invoice_id,
        status=ReviewStatus.PENDING,
        risk_level=normalized_risk,
        reason_codes=reason_codes,
    )
