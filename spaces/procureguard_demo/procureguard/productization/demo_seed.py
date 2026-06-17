"""演示用 mock 采购上下文预置与查询。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import sqlite3
from typing import Any

from procureguard.db import get_connection, initialize_database, seed_policy_documents
from procureguard.db.json_utils import dumps_json, loads_json
from procureguard.models.invoice import ExtractedFields
from procureguard.productization.manual_audit import (
    ExplicitMockProcurementContext,
    ManualLineItem,
    ReceivedLineItem,
)


MOCK_DATA_NOTICE = (
    "PO/GRN data is pre-seeded demo data, not real enterprise records"
)


@dataclass(frozen=True)
class DemoProcurementCase:
    """一条演示发票到 mock PO/GRN 的稳定映射。"""

    case_id: str
    invoice_number: str | None
    vendor_name: str
    vendor_keyword: str
    invoice_amount: float
    po_number: str
    po_amount: float
    currency: str
    grn_number: str | None
    grn_available: bool
    duplicate_existing: bool = False
    submitted_at: str | None = None


DEMO_PROCUREMENT_CASES: tuple[DemoProcurementCase, ...] = (
    DemoProcurementCase(
        case_id="demo_case_a_standard_pass",
        invoice_number="PEGIV-1030765",
        vendor_name="OJC MARKETING SDN BHD",
        vendor_keyword="OJC",
        invoice_amount=193.00,
        po_number="PO-DEMO-001",
        po_amount=193.00,
        currency="MYR",
        grn_number="GRN-DEMO-001",
        grn_available=True,
    ),
    DemoProcurementCase(
        case_id="demo_case_b_amount_mismatch",
        invoice_number=None,
        vendor_name="PERNIAGAAN ZHENG HUI",
        vendor_keyword="ZHENG HUI",
        invoice_amount=436.20,
        po_number="PO-DEMO-002",
        po_amount=400.00,
        currency="MYR",
        grn_number="GRN-DEMO-002",
        grn_available=True,
    ),
    DemoProcurementCase(
        case_id="demo_case_c_duplicate_reject",
        invoice_number="PEGIV-1030531",
        vendor_name="OJC MARKETING SDN BHD",
        vendor_keyword="OJC",
        invoice_amount=170.00,
        po_number="PO-DEMO-003",
        po_amount=170.00,
        currency="MYR",
        grn_number="GRN-DEMO-003",
        grn_available=True,
        duplicate_existing=True,
        submitted_at="2026-01-15",
    ),
)


def seed_demo_procurement_data(
    conn: sqlite3.Connection,
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """向当前数据库预置演示 PO/GRN 和重复发票记录。"""

    _ensure_demo_lookup_table(conn)
    if reset:
        _clear_demo_data(conn)

    for case in DEMO_PROCUREMENT_CASES:
        _upsert_case(conn, case)
    conn.commit()
    return {
        "ready": True,
        "demo_mode": True,
        "seeded_cases": [case.case_id for case in DEMO_PROCUREMENT_CASES],
        "mock_data_notice": MOCK_DATA_NOTICE,
    }


def seed_demo_database_file(
    database_path: str | Path,
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """初始化本地 SQLite 文件并预置演示采购数据。"""

    conn = get_connection(database_path)
    try:
        initialize_database(conn)
        seed_policy_documents(conn)
        result = seed_demo_procurement_data(conn, reset=reset)
        result["database_path"] = str(database_path)
        return result
    finally:
        conn.close()


def resolve_demo_procurement_context(
    database_path: str | Path,
    fields: ExtractedFields,
) -> tuple[ExplicitMockProcurementContext | None, str]:
    """按 invoice_number 优先、vendor keyword 备用查找 demo mock 上下文。"""

    conn = get_connection(database_path)
    try:
        _ensure_demo_lookup_table(conn)
        case = _find_case(conn, fields)
        if case is None:
            return None, "no_po_found"
        context = _context_from_case(conn, case)
        return context, "pre_seeded_mock_po_grn"
    finally:
        conn.close()


def _ensure_demo_lookup_table(conn: sqlite3.Connection) -> None:
    """创建演示映射表，不改变 Phase 2 主链表含义。"""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_invoice_po_lookup (
            case_id TEXT PRIMARY KEY,
            invoice_number TEXT,
            vendor_name TEXT NOT NULL,
            vendor_keyword TEXT NOT NULL,
            invoice_amount REAL NOT NULL,
            po_number TEXT NOT NULL REFERENCES purchase_orders(po_number),
            duplicate_existing INTEGER NOT NULL DEFAULT 0,
            mock_data_notice TEXT NOT NULL
        )
        """
    )
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(demo_invoice_po_lookup)").fetchall()
    }
    if "duplicate_existing" not in columns:
        conn.execute(
            "ALTER TABLE demo_invoice_po_lookup ADD COLUMN duplicate_existing INTEGER NOT NULL DEFAULT 0"
        )


def _clear_demo_data(conn: sqlite3.Connection) -> None:
    """只清理本模块负责的演示记录。"""

    po_numbers = [case.po_number for case in DEMO_PROCUREMENT_CASES]
    placeholders = ",".join("?" for _ in po_numbers)
    conn.execute("DELETE FROM demo_invoice_po_lookup")
    conn.execute(f"DELETE FROM goods_receipts WHERE po_number IN ({placeholders})", po_numbers)
    conn.execute(f"DELETE FROM purchase_orders WHERE po_number IN ({placeholders})", po_numbers)
    conn.execute("DELETE FROM invoices WHERE id LIKE 'demo_duplicate_%'")


def _upsert_case(conn: sqlite3.Connection, case: DemoProcurementCase) -> None:
    """幂等写入一条演示案例。"""

    line_item = {
        "item": "Receipt total",
        "qty": 1,
        "unit_price": case.po_amount,
        "amount": case.po_amount,
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO purchase_orders
        (po_number, vendor_name, total_amount, currency, line_items_json, created_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case.po_number,
            case.vendor_name,
            case.po_amount,
            case.currency,
            dumps_json([line_item]),
            None,
            "open",
        ),
    )
    if case.grn_available and case.grn_number:
        conn.execute(
            """
            INSERT OR REPLACE INTO goods_receipts
            (grn_number, po_number, received_date, line_items_json, receiver)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                case.grn_number,
                case.po_number,
                date(2026, 1, 15).isoformat(),
                dumps_json([{"item": "Receipt total", "received_qty": 1}]),
                "demo.mock.receiver",
            ),
        )
    conn.execute(
        """
        INSERT OR REPLACE INTO demo_invoice_po_lookup
        (case_id, invoice_number, vendor_name, vendor_keyword, invoice_amount, po_number, duplicate_existing, mock_data_notice)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case.case_id,
            case.invoice_number,
            case.vendor_name,
            case.vendor_keyword,
            case.invoice_amount,
            case.po_number,
            1 if case.duplicate_existing else 0,
            MOCK_DATA_NOTICE,
        ),
    )
    if case.duplicate_existing and case.invoice_number:
        conn.execute(
            """
            INSERT OR REPLACE INTO invoices
            (id, file_path, file_hash, upload_time, status, extracted_fields_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"demo_duplicate_{case.invoice_number}",
                f"demo_seed/{case.invoice_number}.json",
                f"demo-duplicate-{case.invoice_number}",
                1768435200,
                "approved",
                dumps_json(
                    {
                        "invoice_number": case.invoice_number,
                        "vendor_name": case.vendor_name,
                        "total_amount": case.invoice_amount,
                        "submitted_at": case.submitted_at,
                    }
                ),
            ),
        )


def _find_case(
    conn: sqlite3.Connection,
    fields: ExtractedFields,
) -> sqlite3.Row | None:
    invoice_number = (fields.invoice_number or "").strip()
    if invoice_number:
        row = conn.execute(
            """
            SELECT * FROM demo_invoice_po_lookup
            WHERE invoice_number = ?
            """,
            (invoice_number,),
        ).fetchone()
        if row is not None:
            return row

    vendor_tokens = _normalize_tokens(fields.vendor_name or "")
    if not vendor_tokens:
        return None
    rows = conn.execute(
        "SELECT * FROM demo_invoice_po_lookup ORDER BY case_id"
    ).fetchall()
    for row in rows:
        keyword_tokens = _normalize_tokens(row["vendor_keyword"])
        vendor_name_tokens = _normalize_tokens(row["vendor_name"])
        if keyword_tokens and keyword_tokens.issubset(vendor_tokens):
            return row
        if vendor_tokens & vendor_name_tokens:
            amount = fields.total_amount
            if amount is None or abs(float(amount) - float(row["invoice_amount"])) <= 0.01:
                return row
    return None


def _context_from_case(
    conn: sqlite3.Connection,
    case: sqlite3.Row,
) -> ExplicitMockProcurementContext:
    po = conn.execute(
        "SELECT * FROM purchase_orders WHERE po_number = ?",
        (case["po_number"],),
    ).fetchone()
    if po is None:
        raise ValueError(f"Pre-seeded demo PO {case['po_number']} was not found.")
    grn_rows = conn.execute(
        "SELECT * FROM goods_receipts WHERE po_number = ? ORDER BY received_date",
        (case["po_number"],),
    ).fetchall()
    po_items = loads_json(po["line_items_json"], [])
    first_grn = grn_rows[0] if grn_rows else None
    grn_items = loads_json(first_grn["line_items_json"], []) if first_grn else []
    return ExplicitMockProcurementContext(
        po_number=po["po_number"],
        po_vendor_name=po["vendor_name"],
        po_total_amount=po["total_amount"],
        po_currency=po["currency"],
        po_status=po["status"],
        po_line_items=[
            ManualLineItem(
                item=item["item"],
                quantity=item.get("qty", 1),
                unit_price=item.get("unit_price"),
                amount=item.get("amount"),
            )
            for item in po_items
        ],
        grn_available=bool(first_grn),
        grn_number=first_grn["grn_number"] if first_grn else None,
        grn_received_date=date.fromisoformat(first_grn["received_date"]) if first_grn else None,
        grn_line_items=[
            ReceivedLineItem(
                item=item["item"],
                received_quantity=item.get("received_qty", 0),
            )
            for item in grn_items
        ],
        duplicate_invoice_exists=bool(case["duplicate_existing"]),
    )


def _normalize_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^A-Z0-9]+", value.upper())
        if len(token) >= 2
    }
