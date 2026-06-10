"""FastAPI 后端基础接口测试。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from procureguard.api.routes import invoice as invoice_route
from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.db import get_connection, initialize_database
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.models.status import InvoiceStatus
from procureguard.repositories import InvoiceRepository


@pytest.fixture()
def client(tmp_path) -> Iterator[TestClient]:
    """为每个测试准备临时数据库和上传目录。"""

    settings = Settings(
        database_path=tmp_path / "procureguard-test.sqlite3",
        upload_dir=tmp_path / "uploads",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def upload_mock_pdf(client: TestClient, content: bytes = b"%PDF-1.4 mock invoice"):
    """以显式 mock 模式上传一份最小 PDF。"""

    return client.post(
        "/invoices/upload",
        params={"processing_mode": "mock"},
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )


def upload_real_pdf(client: TestClient, content: bytes = b"%PDF-1.4 real invoice"):
    """以默认真实规则链上传一份最小 PDF。"""

    return client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )


def build_extracted_fields(
    *,
    invoice_number: str = "INV-API-TEST",
    vendor_name: str = "Acme Office Supplies",
    po_number: str = "PO-1001",
    total_amount: float = 1200.0,
    line_items: list[LineItem] | None = None,
) -> ExtractedFields:
    """构造 API 集成测试使用的已抽取字段。"""

    return ExtractedFields(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        invoice_date="2026-06-10",
        po_number=po_number,
        subtotal=total_amount,
        tax=0.0,
        total_amount=total_amount,
        currency="USD",
        line_items=line_items
        or [
            LineItem(item="Printer Paper", qty=100, unit_price=8.0, amount=800.0),
            LineItem(item="Toner Cartridge", qty=4, unit_price=100.0, amount=400.0),
        ],
        extraction_confidence=0.96,
        extraction_model="api-test-placeholder",
    )


def test_health_returns_ok(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "procureguard"}


def test_upload_pdf_saves_file_and_reaches_review(client: TestClient):
    response = upload_mock_pdf(client)

    assert response.status_code == 200
    payload = response.json()
    invoice = client.get(f"/invoices/{payload['invoice_id']}").json()

    assert payload["status"] == "review"
    assert payload["processing_mode"] == "mock"
    assert invoice["status"] == "review"
    assert invoice["file_hash"] == payload["file_hash"]
    assert invoice["file_path"].endswith(".pdf")
    assert __import__("pathlib").Path(invoice["file_path"]).exists()


def test_uploaded_invoice_can_query_trace_with_mock_steps(client: TestClient):
    invoice_id = upload_mock_pdf(client).json()["invoice_id"]

    response = client.get(f"/invoices/{invoice_id}/trace")
    steps = [item["step_name"] for item in response.json()["items"]]
    outputs = [item["output"] for item in response.json()["items"]]

    assert response.status_code == 200
    assert "extraction" in steps
    assert "validation" in steps
    assert all(output["mode"] == "mock" for output in outputs)


def test_upload_defaults_to_real_agent_chain_and_persists_report(client: TestClient):
    response = upload_real_pdf(client)

    assert response.status_code == 200
    payload = response.json()
    invoice = client.get(f"/invoices/{payload['invoice_id']}").json()
    trace_response = client.get(f"/invoices/{payload['invoice_id']}/trace")
    traces = trace_response.json()["items"]
    steps = [item["step_name"] for item in traces]
    agent_trace = [item for item in traces if item["step_name"] == "agent_call"][0]
    tool_names = [call["name"] for call in agent_trace["tool_calls"]]

    assert payload["processing_mode"] == "real"
    assert payload["status"] == "approved"
    assert invoice["status"] == "approved"
    assert invoice["validation_result"]["po_match"] is True
    assert invoice["validation_result"]["grn_match"] is True
    assert invoice["validation_result"]["duplicate_check"] is True
    assert invoice["audit_report"]["recommended_action"] == "auto_approve"
    assert invoice["audit_report"]["risk_level"] == "low"
    assert steps == ["extraction", "validation", "agent_call", "risk_calc"]
    assert tool_names == [
        "lookup_purchase_order",
        "lookup_goods_receipt",
        "check_duplicate_invoice",
        "retrieve_policy",
    ]
    assert client.get("/review/queue").json()["items"] == []


def test_real_upload_quantity_mismatch_enters_review_queue(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        invoice_route,
        "_build_upload_extracted_fields",
        lambda invoice_id: build_extracted_fields(
            invoice_number=f"INV-MISMATCH-{invoice_id[-8:].upper()}",
            vendor_name="Northwind Industrial",
            po_number="PO-2001",
            total_amount=12500.0,
            line_items=[
                LineItem(item="Safety Gloves", qty=500),
                LineItem(item="Machine Parts", qty=10),
            ],
        ),
    )

    response = upload_real_pdf(client, b"%PDF real quantity mismatch")
    payload = response.json()
    invoice = client.get(f"/invoices/{payload['invoice_id']}").json()
    reviews = client.get("/review/queue").json()["items"]
    traces = client.get(f"/invoices/{payload['invoice_id']}/trace").json()["items"]
    agent_trace = [item for item in traces if item["step_name"] == "agent_call"][0]
    tool_names = [call["name"] for call in agent_trace["tool_calls"]]

    assert response.status_code == 200
    assert payload["processing_mode"] == "real"
    assert invoice["status"] == "review"
    assert invoice["audit_report"]["recommended_action"] == "request_human_approval"
    assert invoice["audit_report"]["risk_level"] in {"medium", "high"}
    assert any(item["field"] == "quantity" for item in invoice["validation_result"]["mismatches"])
    assert any(review["invoice_id"] == payload["invoice_id"] for review in reviews)
    assert tool_names == [
        "lookup_purchase_order",
        "lookup_goods_receipt",
        "check_duplicate_invoice",
        "retrieve_policy",
        "submit_manual_review",
    ]


def test_real_upload_duplicate_invoice_is_rejected(client: TestClient, monkeypatch):
    fixed_fields = build_extracted_fields(invoice_number="INV-API-DUPLICATE")
    monkeypatch.setattr(
        invoice_route,
        "_build_upload_extracted_fields",
        lambda invoice_id: fixed_fields,
    )

    first = upload_real_pdf(client, b"%PDF first duplicate")
    second = upload_real_pdf(client, b"%PDF second duplicate")
    second_payload = second.json()
    duplicate_invoice = client.get(f"/invoices/{second_payload['invoice_id']}").json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second_payload["processing_mode"] == "real"
    assert duplicate_invoice["status"] == "rejected"
    assert duplicate_invoice["validation_result"]["duplicate_check"] is False
    assert duplicate_invoice["audit_report"]["risk_level"] == "high"
    assert duplicate_invoice["audit_report"]["recommended_action"] == "reject"
    assert client.get("/review/queue").json()["items"] == []


def test_invalid_processing_mode_returns_clear_error(client: TestClient):
    response = client.post(
        "/invoices/upload",
        params={"processing_mode": "invalid"},
        files={"file": ("invoice.pdf", b"%PDF invalid mode", "application/pdf")},
    )

    assert response.status_code == 422


def test_upload_creates_pending_review(client: TestClient):
    invoice_id = upload_mock_pdf(client).json()["invoice_id"]

    response = client.get("/review/queue")
    reviews = response.json()["items"]

    assert response.status_code == 200
    assert any(review["invoice_id"] == invoice_id for review in reviews)
    assert all(review["status"] == "pending" for review in reviews)


def test_approved_decision_updates_invoice_status(client: TestClient):
    invoice_id = upload_mock_pdf(client, b"%PDF approved").json()["invoice_id"]
    review = client.get("/review/queue").json()["items"][0]

    decision = client.post(
        f"/review/{review['id']}/decision",
        json={"action": "approved", "comment": "Approved in API test."},
    )
    invoice = client.get(f"/invoices/{invoice_id}").json()

    assert decision.status_code == 200
    assert decision.json()["invoice_status"] == "approved"
    assert invoice["status"] == "approved"


def test_rejected_decision_updates_invoice_status(client: TestClient):
    invoice_id = upload_mock_pdf(client, b"%PDF rejected").json()["invoice_id"]
    review = client.get("/review/queue").json()["items"][0]

    decision = client.post(
        f"/review/{review['id']}/decision",
        json={"action": "rejected", "comment": "Rejected in API test."},
    )
    invoice = client.get(f"/invoices/{invoice_id}").json()

    assert decision.status_code == 200
    assert decision.json()["invoice_status"] == "rejected"
    assert invoice["status"] == "rejected"


def test_resolved_review_cannot_be_decided_twice(client: TestClient):
    upload_mock_pdf(client, b"%PDF repeat decision")
    review = client.get("/review/queue").json()["items"][0]
    first = client.post(
        f"/review/{review['id']}/decision",
        json={"action": "approved", "comment": "First decision."},
    )
    second = client.post(
        f"/review/{review['id']}/decision",
        json={"action": "rejected", "comment": "Second decision."},
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_unsupported_extension_returns_error(client: TestClient):
    response = client.post(
        "/invoices/upload",
        files={"file": ("invoice.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400


def test_empty_upload_returns_error(client: TestClient):
    response = client.post(
        "/invoices/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_duplicate_upload_returns_conflict(client: TestClient):
    content = b"%PDF same content"
    first = upload_mock_pdf(client, content)
    second = upload_mock_pdf(client, content)

    assert first.status_code == 200
    assert second.status_code == 409


def test_missing_invoice_returns_404(client: TestClient):
    response = client.get("/invoices/invoice_missing")

    assert response.status_code == 404


def test_invalid_invoice_transition_fails(tmp_path):
    db_path = tmp_path / "transition.sqlite3"
    conn = get_connection(db_path)
    try:
        initialize_database(conn)
        repo = InvoiceRepository(conn)
        repo.create_invoice("invoice_transition", "mock.pdf", "hash-transition")
        with pytest.raises(ValueError):
            repo.update_status("invoice_transition", InvoiceStatus.APPROVED)
    finally:
        conn.close()


def test_invoice_list_supports_status_filter(client: TestClient):
    invoice_id = upload_mock_pdf(client, b"%PDF list filter").json()["invoice_id"]

    response = client.get("/invoices", params={"status": "review"})
    ids = [item["id"] for item in response.json()["items"]]
    invalid = client.get("/invoices", params={"status": "invalid"})

    assert response.status_code == 200
    assert invoice_id in ids
    assert all(item["status"] == "review" for item in response.json()["items"])
    assert invalid.status_code == 400
