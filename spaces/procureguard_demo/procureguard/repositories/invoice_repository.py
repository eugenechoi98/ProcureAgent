"""发票 SQLite CRUD。"""

import sqlite3
import time
from typing import Any

from procureguard.db.json_utils import dumps_json, loads_json
from procureguard.models.state_flow import validate_invoice_transition
from procureguard.models.status import InvoiceStatus


class InvoiceRepository:
    """封装 invoices 表的基础操作。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_invoice(
        self,
        invoice_id: str,
        file_path: str,
        file_hash: str,
    ) -> dict[str, Any]:
        """创建 pending 发票记录。"""

        try:
            self.conn.execute(
                """
                INSERT INTO invoices (id, file_path, file_hash, upload_time, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    file_path,
                    file_hash,
                    int(time.time()),
                    InvoiceStatus.PENDING.value,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Invoice could not be created: {exc}") from exc
        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            raise RuntimeError(f"Invoice {invoice_id} was not created.")
        return invoice

    def get_invoice(self, invoice_id: str) -> dict[str, Any] | None:
        """按 ID 查询发票。"""

        row = self.conn.execute(
            "SELECT * FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        return self._row_to_invoice(row) if row else None

    def list_invoices(self, status: InvoiceStatus | None = None) -> list[dict[str, Any]]:
        """查询发票列表，可按状态过滤。"""

        if status is None:
            rows = self.conn.execute(
                "SELECT * FROM invoices ORDER BY upload_time DESC, id DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM invoices WHERE status = ? ORDER BY upload_time DESC, id DESC",
                (status.value,),
            ).fetchall()
        return [self._row_to_invoice(row) for row in rows]

    def update_status(
        self,
        invoice_id: str,
        new_status: InvoiceStatus | str,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        """校验并更新发票状态。"""

        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            raise LookupError(f"Invoice {invoice_id} was not found.")

        target_status = InvoiceStatus(new_status)
        validate_invoice_transition(invoice["status"], target_status)
        self.conn.execute(
            "UPDATE invoices SET status = ?, risk_level = COALESCE(?, risk_level) WHERE id = ?",
            (target_status.value, risk_level, invoice_id),
        )
        self.conn.commit()
        updated = self.get_invoice(invoice_id)
        if updated is None:
            raise RuntimeError(f"Invoice {invoice_id} disappeared after status update.")
        return updated

    def get_invoice_by_file_hash(self, file_hash: str) -> dict[str, Any] | None:
        """按文件哈希查询发票。"""

        row = self.conn.execute(
            "SELECT * FROM invoices WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        return self._row_to_invoice(row) if row else None

    def update_extracted_fields(
        self,
        invoice_id: str,
        extracted_fields: dict[str, Any],
    ) -> dict[str, Any]:
        """写入模型抽取字段。"""

        self._ensure_invoice_exists(invoice_id)
        self.conn.execute(
            "UPDATE invoices SET extracted_fields_json = ? WHERE id = ?",
            (dumps_json(extracted_fields), invoice_id),
        )
        self.conn.commit()
        return self._get_existing_invoice(invoice_id)

    def update_validation_result(
        self,
        invoice_id: str,
        validation_result: dict[str, Any],
    ) -> dict[str, Any]:
        """写入确定性校验结果。"""

        self._ensure_invoice_exists(invoice_id)
        self.conn.execute(
            "UPDATE invoices SET validation_result_json = ? WHERE id = ?",
            (dumps_json(validation_result), invoice_id),
        )
        self.conn.commit()
        return self._get_existing_invoice(invoice_id)

    def update_audit_report(
        self,
        invoice_id: str,
        audit_report: dict[str, Any],
    ) -> dict[str, Any]:
        """写入最终审计报告。"""

        self._ensure_invoice_exists(invoice_id)
        self.conn.execute(
            "UPDATE invoices SET audit_report_json = ? WHERE id = ?",
            (dumps_json(audit_report), invoice_id),
        )
        self.conn.commit()
        return self._get_existing_invoice(invoice_id)

    def _ensure_invoice_exists(self, invoice_id: str) -> None:
        """确认发票存在，避免静默写入 0 行。"""

        if self.get_invoice(invoice_id) is None:
            raise LookupError(f"Invoice {invoice_id} was not found.")

    def _get_existing_invoice(self, invoice_id: str) -> dict[str, Any]:
        """返回已经确认存在的发票。"""

        invoice = self.get_invoice(invoice_id)
        if invoice is None:
            raise RuntimeError(f"Invoice {invoice_id} disappeared after update.")
        return invoice

    def _row_to_invoice(self, row: sqlite3.Row) -> dict[str, Any]:
        """把 SQLite 行转换成 API 友好的字典。"""

        return {
            "id": row["id"],
            "file_path": row["file_path"],
            "file_hash": row["file_hash"],
            "upload_time": row["upload_time"],
            "status": row["status"],
            "risk_level": row["risk_level"],
            "extracted_fields": loads_json(row["extracted_fields_json"], None),
            "validation_result": loads_json(row["validation_result_json"], None),
            "audit_report": loads_json(row["audit_report_json"], None),
        }
