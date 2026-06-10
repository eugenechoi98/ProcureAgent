"""共享契约层最小测试。"""

from procureguard.db import initialize_database, seed_mock_data, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.models import (
    AuditReport,
    ExtractedFields,
    GoodsReceiptLookupResult,
    InvalidInvoiceStatusTransition,
    LineItem,
    ManualReviewSubmission,
    PolicySearchResult,
    PurchaseOrderLookupResult,
    RecommendedAction,
    RiskLevel,
    ValidationResult,
    can_transition_invoice,
    validate_invoice_transition,
)
from procureguard.services import PolicyRAG, ThreeWayMatcher
from procureguard.tools import (
    check_duplicate_invoice,
    lookup_goods_receipt,
    lookup_purchase_order,
    retrieve_policy,
    submit_manual_review,
)


def build_conn():
    """准备内存数据库和 mock 数据。"""

    conn = get_connection(":memory:")
    initialize_database(conn)
    seed_mock_data(conn)
    seed_policy_documents(conn)
    return conn


def test_models_and_state_flow_contracts():
    invoice = ExtractedFields(
        vendor_name="Acme Office Supplies",
        invoice_number="INV-1001",
        po_number="PO-1001",
        total_amount=1200.0,
        line_items=[LineItem(item="Printer Paper", qty=100)],
        extraction_confidence=0.95,
        extraction_model="mock-v1",
    )
    report = AuditReport(
        invoice_id="invoice_1",
        vendor=invoice.vendor_name,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        po_match=True,
        goods_receipt_match=True,
        policy_flags=[],
        risk_level=RiskLevel.LOW,
        recommended_action=RecommendedAction.AUTO_APPROVE,
        evidence=[],
        anomaly_explanation="No anomaly found.",
        trace_id="trace_1",
    )

    assert report.vendor == "Acme Office Supplies"
    assert can_transition_invoice("pending", "processing")
    assert not can_transition_invoice("approved", "review")


def test_list_defaults_are_not_shared_between_instances():
    first_invoice = ExtractedFields(extraction_confidence=0.9, extraction_model="mock")
    second_invoice = ExtractedFields(extraction_confidence=0.8, extraction_model="mock")
    first_invoice.line_items.append(LineItem(item="Paper", qty=1))

    first_report = AuditReport(
        invoice_id="invoice_1",
        vendor="Vendor A",
        total_amount=10.0,
        currency="USD",
        po_match=True,
        goods_receipt_match=True,
        risk_level=RiskLevel.LOW,
        recommended_action=RecommendedAction.AUTO_APPROVE,
        anomaly_explanation="No anomaly found.",
        trace_id="trace_1",
    )
    second_report = AuditReport(
        invoice_id="invoice_2",
        vendor="Vendor B",
        total_amount=20.0,
        currency="USD",
        po_match=True,
        goods_receipt_match=True,
        risk_level=RiskLevel.LOW,
        recommended_action=RecommendedAction.AUTO_APPROVE,
        anomaly_explanation="No anomaly found.",
        trace_id="trace_2",
    )
    first_report.policy_flags.append("manual_review_required")

    assert second_invoice.line_items == []
    assert second_report.policy_flags == []


def test_schema_initialization_is_repeatable_and_policy_seed_works():
    conn = get_connection(":memory:")
    initialize_database(conn)
    initialize_database(conn)
    seed_policy_documents(conn)

    count = conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0]

    assert count == 10


def test_invalid_state_transition_raises_clear_error():
    try:
        validate_invoice_transition("approved", "review")
    except InvalidInvoiceStatusTransition as exc:
        assert "approved -> review" in str(exc)
    else:
        raise AssertionError("Expected invalid state transition to raise.")


def test_sqlite_tools_and_policy_rag_contracts():
    conn = build_conn()

    po_result = lookup_purchase_order(conn, "PO-1001")
    grn_result = lookup_goods_receipt(conn, "PO-1001")
    policies = retrieve_policy(conn, "duplicate invoice", top_k=2)
    duplicate = check_duplicate_invoice(
        conn,
        invoice_number="INV-DUP-001",
        vendor_name="Acme Office Supplies",
    )

    assert po_result.found
    assert grn_result.found
    assert policies[0].section == "duplicate_invoice"
    assert duplicate.is_duplicate
    assert duplicate.duplicate_check is False


def test_all_five_tool_interfaces_exist_and_return_contracts():
    conn = build_conn()

    po_result = lookup_purchase_order(conn, "PO-1001")
    grn_result = lookup_goods_receipt(conn, "PO-1001")
    policies = retrieve_policy(conn, "duplicate invoice", top_k=1)
    duplicate = check_duplicate_invoice(
        conn,
        invoice_number="INV-DUP-001",
        vendor_name="Acme Office Supplies",
    )
    submission = submit_manual_review(
        conn,
        invoice_id="invoice_existing_duplicate",
        risk_level=RiskLevel.MEDIUM,
        reason_codes=["duplicate_invoice"],
    )

    assert isinstance(po_result, PurchaseOrderLookupResult)
    assert isinstance(grn_result, GoodsReceiptLookupResult)
    assert isinstance(policies[0], PolicySearchResult)
    assert isinstance(duplicate.is_duplicate, bool)
    assert isinstance(submission, ManualReviewSubmission)


def test_audit_report_does_not_depend_on_context_pack():
    fields = AuditReport.model_fields

    assert "context_pack" not in fields
    assert AuditReport.__name__ == "AuditReport"


def test_validation_duplicate_check_can_be_explicitly_rewritten_false():
    validation = ValidationResult(
        po_match=True,
        grn_match=True,
        amount_match=True,
        duplicate_check=True,
    )
    validation.duplicate_check = False

    assert validation.duplicate_check is False


def test_validator_policy_flags_and_manual_review():
    conn = build_conn()
    po = lookup_purchase_order(conn, "PO-2001").purchase_order
    grn = lookup_goods_receipt(conn, "PO-2001").receipts[0]
    invoice = ExtractedFields(
        vendor_name="Northwind Industrial",
        invoice_number="INV-2001",
        po_number="PO-2001",
        total_amount=12500.0,
        line_items=[
            LineItem(item="Safety Gloves", qty=500),
            LineItem(item="Machine Parts", qty=10),
        ],
        extraction_confidence=0.90,
        extraction_model="mock-v1",
    )

    validation = ThreeWayMatcher().match(
        invoice=invoice,
        po=po.model_dump(),
        grn=grn.model_dump(),
    )
    flags = PolicyRAG(conn).check_policy_violation(invoice, validation)
    submission = submit_manual_review(
        conn,
        invoice_id="invoice_existing_duplicate",
        risk_level=RiskLevel.HIGH,
        reason_codes=flags,
    )

    assert not validation.grn_match
    assert "goods_receipt_mismatch" in flags
    assert "high_value_approval_required" in flags
    assert submission.status == "pending"
