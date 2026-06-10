"""FastAPI 后端基础接口测试。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.db import get_connection, initialize_database
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
    """上传一份最小 mock PDF。"""

    return client.post(
        "/invoices/upload",
        files={"file": ("invoice.pdf", content, "application/pdf")},
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
