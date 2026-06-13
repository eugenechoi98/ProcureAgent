"""查询采购订单工具。"""

import sqlite3

from procureguard.db.json_utils import loads_json
from procureguard.models.invoice import PurchaseOrder
from procureguard.models.tools import PurchaseOrderLookupResult


def lookup_purchase_order(
    conn: sqlite3.Connection,
    po_number: str,
) -> PurchaseOrderLookupResult:
    """按 PO 编号查询 mock 采购订单。"""

    row = conn.execute(
        "SELECT * FROM purchase_orders WHERE po_number = ?",
        (po_number,),
    ).fetchone()
    if row is None:
        return PurchaseOrderLookupResult(
            found=False,
            po_number=po_number,
            message=f"Purchase order {po_number} was not found.",
        )

    po = PurchaseOrder(
        po_number=row["po_number"],
        vendor_name=row["vendor_name"],
        total_amount=row["total_amount"],
        currency=row["currency"],
        line_items=loads_json(row["line_items_json"], []),
        created_date=row["created_date"],
        status=row["status"],
    )
    return PurchaseOrderLookupResult(
        found=True,
        po_number=po_number,
        purchase_order=po,
        message=f"Purchase order {po_number} was found.",
    )
