"""重复发票检测工具。"""

import sqlite3

from procureguard.db.json_utils import loads_json
from procureguard.models.tools import DuplicateCheckResult


def check_duplicate_invoice(
    conn: sqlite3.Connection,
    invoice_number: str,
    vendor_name: str,
    current_invoice_id: str | None = None,
) -> DuplicateCheckResult:
    """按供应商和发票号检查重复提交。"""

    rows = conn.execute(
        """
        SELECT id, extracted_fields_json
        FROM invoices
        WHERE extracted_fields_json IS NOT NULL
        """,
    ).fetchall()
    matched_ids: list[str] = []
    for row in rows:
        if current_invoice_id and row["id"] == current_invoice_id:
            continue
        fields = loads_json(row["extracted_fields_json"], {})
        same_invoice = fields.get("invoice_number") == invoice_number
        same_vendor = fields.get("vendor_name") == vendor_name
        if same_invoice and same_vendor:
            matched_ids.append(row["id"])

    is_duplicate = bool(matched_ids)
    return DuplicateCheckResult(
        is_duplicate=is_duplicate,
        duplicate_check=not is_duplicate,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        matched_invoice_ids=matched_ids,
        message="Duplicate invoice found." if is_duplicate else "No duplicate invoice found.",
    )
