"""查询收货记录工具。"""

import sqlite3

from procureguard.db.json_utils import loads_json
from procureguard.models.invoice import GoodsReceipt
from procureguard.models.tools import GoodsReceiptLookupResult


def lookup_goods_receipt(
    conn: sqlite3.Connection,
    po_number: str,
) -> GoodsReceiptLookupResult:
    """按 PO 编号查询收货记录。"""

    rows = conn.execute(
        "SELECT * FROM goods_receipts WHERE po_number = ? ORDER BY received_date",
        (po_number,),
    ).fetchall()
    receipts = [
        GoodsReceipt(
            grn_number=row["grn_number"],
            po_number=row["po_number"],
            received_date=row["received_date"],
            line_items=loads_json(row["line_items_json"], []),
            receiver=row["receiver"],
        )
        for row in rows
    ]
    return GoodsReceiptLookupResult(
        found=bool(receipts),
        po_number=po_number,
        receipts=receipts,
        message=f"Found {len(receipts)} goods receipt record(s) for {po_number}.",
    )
