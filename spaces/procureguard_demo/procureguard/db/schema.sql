-- ProcureGuard AI 共享 SQLite schema

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    upload_time INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','processing','approved','rejected','review')),
    risk_level TEXT CHECK (risk_level IS NULL OR risk_level IN ('low','medium','high')),
    extracted_fields_json TEXT,
    validation_result_json TEXT,
    audit_report_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_file_hash ON invoices(file_hash);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_number TEXT PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    total_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    line_items_json TEXT NOT NULL,
    created_date TEXT,
    status TEXT NOT NULL CHECK (status IN ('open','closed','cancelled'))
);

CREATE TABLE IF NOT EXISTS goods_receipts (
    grn_number TEXT PRIMARY KEY,
    po_number TEXT NOT NULL REFERENCES purchase_orders(po_number),
    received_date TEXT NOT NULL,
    line_items_json TEXT NOT NULL,
    receiver TEXT
);

CREATE TABLE IF NOT EXISTS audit_traces (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    step_name TEXT NOT NULL CHECK (step_name IN ('extraction','validation','agent_call','risk_calc')),
    input_json TEXT,
    output_json TEXT,
    tool_calls_json TEXT,
    latency_ms INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low','medium','high')),
    reason_codes_json TEXT NOT NULL,
    evidence_json TEXT,
    assigned_to TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')),
    reviewer_comment TEXT,
    created_at INTEGER NOT NULL,
    resolved_at INTEGER
);

CREATE TABLE IF NOT EXISTS policy_documents (
    id TEXT PRIMARY KEY,
    section TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
    content,
    section,
    content='policy_documents',
    content_rowid='rowid'
);
