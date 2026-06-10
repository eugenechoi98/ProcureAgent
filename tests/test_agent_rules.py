"""Phase 2 Agent 与规则闭环测试。"""

from procureguard.db import initialize_database, seed_mock_data, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.models.status import RecommendedAction, RiskLevel
from procureguard.repositories import AuditTraceRepository, InvoiceRepository, ReviewRepository
from procureguard.services import AgentInvoiceProcessor, RiskEngine


def build_conn():
    """准备 Agent 规则测试数据库。"""

    conn = get_connection(":memory:")
    initialize_database(conn)
    seed_mock_data(conn)
    seed_policy_documents(conn)
    return conn


def create_pending_invoice(conn, invoice_id: str = "invoice_agent"):
    """创建待处理发票记录。"""

    return InvoiceRepository(conn).create_invoice(
        invoice_id=invoice_id,
        file_path=f"mock/{invoice_id}.pdf",
        file_hash=f"hash-{invoice_id}",
    )


def test_agent_auto_approves_clean_three_way_match():
    conn = build_conn()
    create_pending_invoice(conn, "invoice_clean")
    invoice = ExtractedFields(
        vendor_name="Acme Office Supplies",
        invoice_number="INV-CLEAN-001",
        invoice_date="2026-06-10",
        po_number="PO-1001",
        total_amount=1200.0,
        line_items=[
            LineItem(item="Printer Paper", qty=100),
            LineItem(item="Toner Cartridge", qty=4),
        ],
        extraction_confidence=0.97,
        extraction_model="mock-v1",
    )

    report = AgentInvoiceProcessor(conn).process_extracted_invoice("invoice_clean", invoice)
    stored = InvoiceRepository(conn).get_invoice("invoice_clean")
    traces = AuditTraceRepository(conn).list_traces("invoice_clean")

    assert report.risk_level == RiskLevel.LOW
    assert report.recommended_action == RecommendedAction.AUTO_APPROVE
    assert stored["status"] == "approved"
    assert stored["risk_level"] == "low"
    assert stored["validation_result"]["duplicate_check"] is True
    assert stored["audit_report"]["recommended_action"] == "auto_approve"
    assert [trace["step_name"] for trace in traces] == [
        "extraction",
        "validation",
        "agent_call",
        "risk_calc",
    ]


def test_agent_submits_manual_review_for_quantity_mismatch():
    conn = build_conn()
    create_pending_invoice(conn, "invoice_mismatch")
    invoice = ExtractedFields(
        vendor_name="Northwind Industrial",
        invoice_number="INV-MISMATCH-001",
        invoice_date="2026-06-10",
        po_number="PO-2001",
        total_amount=12500.0,
        line_items=[
            LineItem(item="Safety Gloves", qty=500),
            LineItem(item="Machine Parts", qty=10),
        ],
        extraction_confidence=0.93,
        extraction_model="mock-v1",
    )

    report = AgentInvoiceProcessor(conn).process_extracted_invoice("invoice_mismatch", invoice)
    stored = InvoiceRepository(conn).get_invoice("invoice_mismatch")
    reviews = ReviewRepository(conn).list_pending_reviews()
    agent_trace = [
        trace
        for trace in AuditTraceRepository(conn).list_traces("invoice_mismatch")
        if trace["step_name"] == "agent_call"
    ][0]
    tool_names = [call["name"] for call in agent_trace["tool_calls"]]

    assert report.risk_level == RiskLevel.MEDIUM
    assert report.recommended_action == RecommendedAction.REQUEST_HUMAN_APPROVAL
    assert "goods_receipt_mismatch" in report.policy_flags
    assert "high_value_approval_required" in report.policy_flags
    assert stored["status"] == "review"
    assert any(review["invoice_id"] == "invoice_mismatch" for review in reviews)
    assert tool_names == [
        "lookup_purchase_order",
        "lookup_goods_receipt",
        "check_duplicate_invoice",
        "retrieve_policy",
        "submit_manual_review",
    ]


def test_agent_rejects_duplicate_and_rewrites_validation_result():
    conn = build_conn()
    create_pending_invoice(conn, "invoice_duplicate")
    invoice = ExtractedFields(
        vendor_name="Acme Office Supplies",
        invoice_number="INV-DUP-001",
        invoice_date="2026-06-10",
        po_number="PO-1001",
        total_amount=1200.0,
        line_items=[
            LineItem(item="Printer Paper", qty=100),
            LineItem(item="Toner Cartridge", qty=4),
        ],
        extraction_confidence=0.95,
        extraction_model="mock-v1",
    )

    report = AgentInvoiceProcessor(conn).process_extracted_invoice("invoice_duplicate", invoice)
    stored = InvoiceRepository(conn).get_invoice("invoice_duplicate")

    assert report.risk_level == RiskLevel.HIGH
    assert report.recommended_action == RecommendedAction.REJECT
    assert "duplicate_invoice" in report.policy_flags
    assert stored["status"] == "rejected"
    assert stored["risk_level"] == "high"
    assert stored["validation_result"]["duplicate_check"] is False
    assert stored["audit_report"]["risk_level"] == "high"


def test_risk_engine_keeps_duplicate_as_high_risk():
    validation = type(
        "ValidationLike",
        (),
        {
            "po_match": True,
            "grn_match": True,
            "amount_match": True,
            "duplicate_check": False,
        },
    )()
    invoice = ExtractedFields(
        extraction_confidence=0.9,
        extraction_model="mock-v1",
    )

    assessment = RiskEngine().assess(invoice, validation, ["duplicate_invoice"])

    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.recommended_action == RecommendedAction.REJECT
