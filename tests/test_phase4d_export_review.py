"""Phase 4D AuditReport 导出与人工复核 API 测试。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "samples" / "manual_audit"


@pytest.fixture()
def client(tmp_path: Path):
    """创建隔离应用和进程内 manual audit store。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def create_audit(client: TestClient, filename: str) -> dict:
    """提交一条内置 manual audit 请求。"""

    payload = json.loads((SAMPLE_DIR / filename).read_text(encoding="utf-8"))
    response = client.post("/api/mvp/manual-audit", json=payload)
    assert response.status_code == 200
    return response.json()


def test_manual_audit_exports_parseable_json_with_boundaries(client: TestClient) -> None:
    audit = create_audit(client, "request_amount_mismatch.json")
    response = client.get(
        f"/api/mvp/manual-audit/{audit['audit_id']}/export",
        params={"format": "json"},
    )
    payload = json.loads(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert payload["risk_level"] == "medium"
    assert payload["recommended_action"] == "request_human_approval"
    assert payload["payment_authority"] is False
    assert payload["review_status"] == "pending"
    assert payload["fallback_status"] == {"reason": None, "used": False}
    assert payload["source_labels"]["risk_decision_source"] == "deterministic_rules"
    assert payload["source_labels"]["explanation_source"] == "deterministic_template"
    assert payload["procurement_context_summary"]["context_source"] == "explicit_mock_context"


def test_manual_audit_exports_readable_markdown(client: TestClient) -> None:
    audit = create_audit(client, "request_missing_grn.json")
    response = client.get(
        f"/api/mvp/manual-audit/{audit['audit_id']}/export",
        params={"format": "markdown"},
    )
    text = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Risk level: `medium`" in text
    assert "Recommended action: `request_human_approval`" in text
    assert "Invoice field source: `manual_input`" in text
    assert "Procurement context source: `explicit_mock_context`" in text
    assert "Fallback used: `false`" in text
    assert "Payment authority: `false`" in text
    assert "not a financial payment instrument" in text


def test_review_queue_contains_manual_review_cases_only(client: TestClient) -> None:
    low = create_audit(client, "request_standard_pass.json")
    medium = create_audit(client, "request_amount_mismatch.json")
    queue = client.get("/api/mvp/manual-audit/review-queue").json()
    ids = [item["audit_id"] for item in queue["items"]]

    assert medium["audit_id"] in ids
    assert low["audit_id"] not in ids
    assert queue["payment_authority"] is False
    assert queue["persistence"] == "process_memory_only"


@pytest.mark.parametrize("decision", ["approve", "reject", "request_more_info"])
def test_reviewer_decision_is_supported_and_does_not_mutate_rules(
    client: TestClient,
    decision: str,
) -> None:
    audit = create_audit(client, "request_amount_mismatch.json")
    original = (audit["risk_level"], audit["recommended_action"])
    response = client.post(
        f"/api/mvp/manual-audit/{audit['audit_id']}/review",
        json={"decision": decision, "reviewer_note": "Need PO owner confirmation."},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["review_status"] == "resolved"
    assert payload["review_decision"] == decision
    assert payload["reviewer_note"] == "Need PO owner confirmation."
    assert (payload["risk_level"], payload["recommended_action"]) == original
    assert payload["deterministic_result_unchanged"] is True
    assert payload["source_labels"]["live_layoutlmv3_used"] is False
    assert payload["source_labels"]["live_lora_used"] is False


def test_reviewer_note_appears_in_both_exports(client: TestClient) -> None:
    audit = create_audit(client, "request_missing_grn.json")
    review = client.post(
        f"/api/mvp/manual-audit/{audit['audit_id']}/review",
        json={"decision": "request_more_info", "reviewer_note": "Confirm receiving record."},
    )
    assert review.status_code == 200

    json_export = client.get(
        f"/api/mvp/manual-audit/{audit['audit_id']}/export?format=json"
    ).json()
    markdown_export = client.get(
        f"/api/mvp/manual-audit/{audit['audit_id']}/export?format=markdown"
    ).text

    assert json_export["review_decision"] == "request_more_info"
    assert json_export["reviewer_note"] == "Confirm receiving record."
    assert json_export["risk_level"] == "medium"
    assert json_export["recommended_action"] == "request_human_approval"
    assert "Reviewer note: `Confirm receiving record.`" in markdown_export
    assert "Deterministic result unchanged: `true`" in markdown_export


def test_resolved_review_leaves_pending_queue(client: TestClient) -> None:
    audit = create_audit(client, "request_amount_mismatch.json")
    client.post(
        f"/api/mvp/manual-audit/{audit['audit_id']}/review",
        json={"decision": "approve", "reviewer_note": "Local demo decision."},
    )
    ids = [
        item["audit_id"]
        for item in client.get("/api/mvp/manual-audit/review-queue").json()["items"]
    ]

    assert audit["audit_id"] not in ids


def test_invalid_export_format_and_unknown_audit_are_clear(client: TestClient) -> None:
    audit = create_audit(client, "request_standard_pass.json")
    invalid = client.get(
        f"/api/mvp/manual-audit/{audit['audit_id']}/export",
        params={"format": "pdf"},
    )
    missing = client.get("/api/mvp/manual-audit/manual_missing/export?format=json")

    assert invalid.status_code == 422
    assert "format" in invalid.text
    assert missing.status_code == 404
    assert "was not found" in missing.json()["detail"]


def test_low_risk_audit_cannot_receive_fake_required_review(client: TestClient) -> None:
    audit = create_audit(client, "request_standard_pass.json")
    response = client.post(
        f"/api/mvp/manual-audit/{audit['audit_id']}/review",
        json={"decision": "approve", "reviewer_note": "Not required."},
    )

    assert response.status_code == 400
    assert "does not require human review" in response.json()["detail"]


def test_blank_reviewer_note_is_rejected(client: TestClient) -> None:
    audit = create_audit(client, "request_amount_mismatch.json")
    response = client.post(
        f"/api/mvp/manual-audit/{audit['audit_id']}/review",
        json={"decision": "approve", "reviewer_note": "   "},
    )

    assert response.status_code == 422
    assert "reviewer_note" in response.text
