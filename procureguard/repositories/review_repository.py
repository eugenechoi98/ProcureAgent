"""人工审核队列 SQLite CRUD。"""

import sqlite3
import time
from typing import Any

from procureguard.db.json_utils import loads_json
from procureguard.models.status import InvoiceStatus, ReviewStatus
from procureguard.repositories.invoice_repository import InvoiceRepository


class ReviewRepository:
    """封装 review_queue 表的基础操作。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_pending_reviews(self) -> list[dict[str, Any]]:
        """查询 pending 人工审核队列。"""

        rows = self.conn.execute(
            """
            SELECT * FROM review_queue
            WHERE status = ?
            ORDER BY created_at ASC, id ASC
            """,
            (ReviewStatus.PENDING.value,),
        ).fetchall()
        return [self._row_to_review(row) for row in rows]

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        """按 ID 查询审核任务。"""

        row = self.conn.execute(
            "SELECT * FROM review_queue WHERE id = ?",
            (review_id,),
        ).fetchone()
        return self._row_to_review(row) if row else None

    def submit_decision(
        self,
        review_id: str,
        action: str,
        comment: str | None,
    ) -> dict[str, Any]:
        """提交人工审核决定，并同步更新发票状态。"""

        if action not in {ReviewStatus.APPROVED.value, ReviewStatus.REJECTED.value}:
            raise ValueError("Review action must be 'approved' or 'rejected'.")

        review = self.get_review(review_id)
        if review is None:
            raise LookupError(f"Review {review_id} was not found.")
        if review["status"] != ReviewStatus.PENDING.value:
            raise RuntimeError(f"Review {review_id} has already been resolved.")

        resolved_at = int(time.time())
        self.conn.execute(
            """
            UPDATE review_queue
            SET status = ?, reviewer_comment = ?, resolved_at = ?
            WHERE id = ?
            """,
            (action, comment, resolved_at, review_id),
        )

        invoice_status = (
            InvoiceStatus.APPROVED
            if action == ReviewStatus.APPROVED.value
            else InvoiceStatus.REJECTED
        )
        invoice = InvoiceRepository(self.conn).update_status(
            review["invoice_id"],
            invoice_status,
        )
        self.conn.commit()

        updated_review = self.get_review(review_id)
        if updated_review is None:
            raise RuntimeError(f"Review {review_id} disappeared after decision.")
        return {
            "review": updated_review,
            "invoice_status": invoice["status"],
        }

    def _row_to_review(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "invoice_id": row["invoice_id"],
            "risk_level": row["risk_level"],
            "reason_codes": loads_json(row["reason_codes_json"], []),
            "evidence": loads_json(row["evidence_json"], []),
            "assigned_to": row["assigned_to"],
            "status": row["status"],
            "reviewer_comment": row["reviewer_comment"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
        }
