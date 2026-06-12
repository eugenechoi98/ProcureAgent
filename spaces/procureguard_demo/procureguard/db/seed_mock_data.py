"""采购订单、收货记录和重复发票 mock 数据。"""

import sqlite3
import time

from procureguard.db.json_utils import dumps_json

MOCK_PURCHASE_ORDERS = [
    {
        "po_number": "PO-1001",
        "vendor_name": "Acme Office Supplies",
        "total_amount": 1200.00,
        "currency": "USD",
        "line_items": [
            {"item": "Printer Paper", "qty": 100, "unit_price": 8.0, "amount": 800.0},
            {"item": "Toner Cartridge", "qty": 4, "unit_price": 100.0, "amount": 400.0},
        ],
        "created_date": "2026-05-20",
        "status": "open",
    },
    {
        "po_number": "PO-2001",
        "vendor_name": "Northwind Industrial",
        "total_amount": 12500.00,
        "currency": "USD",
        "line_items": [
            {"item": "Safety Gloves", "qty": 500, "unit_price": 5.0, "amount": 2500.0},
            {"item": "Machine Parts", "qty": 10, "unit_price": 1000.0, "amount": 10000.0},
        ],
        "created_date": "2026-05-25",
        "status": "open",
    },
]

MOCK_GOODS_RECEIPTS = [
    {
        "grn_number": "GRN-1001",
        "po_number": "PO-1001",
        "received_date": "2026-05-28",
        "line_items": [
            {"item": "Printer Paper", "received_qty": 100},
            {"item": "Toner Cartridge", "received_qty": 4},
        ],
        "receiver": "finance.ops",
    },
    {
        "grn_number": "GRN-2001",
        "po_number": "PO-2001",
        "received_date": "2026-05-30",
        "line_items": [
            {"item": "Safety Gloves", "received_qty": 500},
            {"item": "Machine Parts", "received_qty": 8},
        ],
        "receiver": "warehouse.ops",
    },
]


def seed_mock_data(conn: sqlite3.Connection) -> None:
    """初始化 PO、GRN 和一条重复检测用发票。"""

    for po in MOCK_PURCHASE_ORDERS:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchase_orders
            (po_number, vendor_name, total_amount, currency, line_items_json, created_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                po["po_number"],
                po["vendor_name"],
                po["total_amount"],
                po["currency"],
                dumps_json(po["line_items"]),
                po["created_date"],
                po["status"],
            ),
        )

    for grn in MOCK_GOODS_RECEIPTS:
        conn.execute(
            """
            INSERT OR IGNORE INTO goods_receipts
            (grn_number, po_number, received_date, line_items_json, receiver)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                grn["grn_number"],
                grn["po_number"],
                grn["received_date"],
                dumps_json(grn["line_items"]),
                grn["receiver"],
            ),
        )

    duplicate_fields = {
        "vendor_name": "Acme Office Supplies",
        "invoice_number": "INV-DUP-001",
        "invoice_date": "2026-06-01",
        "po_number": "PO-1001",
        "total_amount": 1200.00,
        "currency": "USD",
        "line_items": [],
        "extraction_confidence": 0.98,
        "extraction_model": "mock-v1",
    }
    conn.execute(
        """
        INSERT OR IGNORE INTO invoices
        (id, file_path, file_hash, upload_time, status, extracted_fields_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "invoice_existing_duplicate",
            "mock/invoice_existing_duplicate.pdf",
            "mock_hash_existing_duplicate",
            int(time.time()),
            "approved",
            dumps_json(duplicate_fields),
        ),
    )
    conn.commit()
