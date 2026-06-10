"""Policy RAG mock 政策数据。"""

import sqlite3
import time

MOCK_POLICIES = [
    {
        "section": "approval_threshold",
        "content": "Invoice approval limit: invoices exceeding USD 10,000 require department manager approval before payment processing.",
    },
    {
        "section": "approval_threshold",
        "content": "Invoice approval limit: invoices exceeding USD 50,000 require both department manager and CFO approval.",
    },
    {
        "section": "three_way_match",
        "content": "All invoices must be matched against a valid Purchase Order (PO) and Goods Receipt Note (GRN) before approval. Invoices without a matching PO number will be automatically flagged for review.",
    },
    {
        "section": "duplicate_invoice",
        "content": "Duplicate invoices, identified by matching invoice number and vendor name, must be rejected immediately. Vendor must resubmit with a corrected invoice number.",
    },
    {
        "section": "quantity_tolerance",
        "content": "Quantity discrepancies between invoice and GRN exceeding 0% are not permitted. Any quantity mismatch requires manual review and vendor confirmation.",
    },
    {
        "section": "amount_tolerance",
        "content": "Invoice amount may differ from PO amount by no more than 1%. Discrepancies exceeding this threshold require procurement team review.",
    },
    {
        "section": "payment_terms",
        "content": "Standard payment terms are Net 30 days from invoice receipt. Early payment discounts must be approved by Finance before processing.",
    },
    {
        "section": "vendor_validation",
        "content": "All vendors must be registered in the approved vendor list before invoice processing. Invoices from unregistered vendors will be held pending vendor onboarding.",
    },
    {
        "section": "currency",
        "content": "Multi-currency invoices must include the applicable exchange rate on the invoice date. Finance team will verify rates against the official corporate FX rate table.",
    },
    {
        "section": "missing_fields",
        "content": "Invoices missing mandatory fields (invoice number, date, vendor name, PO number, total amount) will be returned to vendor for correction.",
    },
]


def seed_policy_documents(conn: sqlite3.Connection) -> None:
    """初始化政策文档并重建 FTS 索引。"""

    now = int(time.time())
    for index, policy in enumerate(MOCK_POLICIES, start=1):
        conn.execute(
            """
            INSERT OR IGNORE INTO policy_documents (id, section, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (f"policy_{index:03d}", policy["section"], policy["content"], now),
        )
    conn.execute("INSERT INTO policy_fts(policy_fts) VALUES ('rebuild')")
    conn.commit()
