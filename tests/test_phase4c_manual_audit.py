"""Phase 4C 手动字段与显式 mock 上下文测试。"""

from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.db.connection import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "samples" / "manual_audit"


@pytest.fixture()
def client(tmp_path: Path):
    """创建使用临时默认数据库的 API 客户端。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client, settings


def load_request(name: str) -> dict:
    """读取一条 synthetic manual audit 请求。"""

    return json.loads((SAMPLE_DIR / name).read_text(encoding="utf-8"))


def post_case(client: TestClient, name: str):
    """提交内置手动审核场景。"""

    return client.post("/api/mvp/manual-audit", json=load_request(name))


def test_manual_audit_standard_pass_and_source_labels(client) -> None:
    test_client, _ = client
    response = post_case(test_client, "request_standard_pass.json")
    payload = response.json()

    assert response.status_code == 200
    assert payload["risk_level"] == "low"
    assert payload["recommended_action"] == "auto_approve"
    assert payload["audit_report"]["po_match"] is True
    assert payload["audit_report"]["goods_receipt_match"] is True
    assert payload["source_labels"] == {
        "invoice_field_source": "manual_input",
        "procurement_context_source": "explicit_mock_context",
        "risk_decision_source": "deterministic_rules",
        "explanation_source": "deterministic_template",
        "live_layoutlmv3_used": False,
        "live_lora_used": False,
        "payment_authority": False,
    }
    assert payload["explanation_mode_used"] == "template"
    assert payload["fallback_status"] == {"used": False, "reason": None}
    assert payload["audit_report"]["explanation"]["used_rewrite"] is False


def test_manual_audit_amount_mismatch_uses_rule_result(client) -> None:
    test_client, _ = client
    payload = post_case(test_client, "request_amount_mismatch.json").json()

    assert payload["risk_level"] == "medium"
    assert payload["recommended_action"] == "request_human_approval"
    assert "amount_discrepancy" in payload["audit_report"]["policy_flags"]
    assert any(item["field"] == "total_amount" for item in payload["audit_report"]["evidence"])


def test_manual_audit_missing_grn_enters_review(client) -> None:
    test_client, _ = client
    payload = post_case(test_client, "request_missing_grn.json").json()

    assert payload["risk_level"] == "medium"
    assert payload["recommended_action"] == "request_human_approval"
    assert payload["audit_report"]["goods_receipt_match"] is False
    assert "goods_receipt_mismatch" in payload["audit_report"]["policy_flags"]


def test_manual_audit_duplicate_flag_rejects(client) -> None:
    test_client, _ = client
    request = load_request("request_standard_pass.json")
    request["procurement_context"]["duplicate_invoice_exists"] = True
    payload = test_client.post("/api/mvp/manual-audit", json=request).json()

    assert payload["risk_level"] == "high"
    assert payload["recommended_action"] == "reject"
    assert "duplicate_invoice" in payload["audit_report"]["policy_flags"]


@pytest.mark.parametrize(
    ("mutator", "field_fragment"),
    [
        (lambda data: data["invoice_fields"].update(total_amount=-1), "total_amount"),
        (lambda data: data["invoice_fields"].pop("vendor_name"), "vendor_name"),
        (lambda data: data["invoice_fields"].update(invoice_date="15/06/2026"), "invoice_date"),
        (lambda data: data["invoice_fields"].update(currency="US"), "currency"),
    ],
)
def test_manual_audit_rejects_invalid_input(client, mutator, field_fragment) -> None:
    test_client, _ = client
    request = load_request("request_standard_pass.json")
    mutator(request)
    response = test_client.post("/api/mvp/manual-audit", json=request)

    assert response.status_code == 422
    assert field_fragment in response.text


def test_manual_audit_does_not_pollute_app_database(client) -> None:
    test_client, settings = client
    conn = get_connection(settings.database_path)
    try:
        before = {
            "invoices": conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            "purchase_orders": conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0],
            "goods_receipts": conn.execute("SELECT COUNT(*) FROM goods_receipts").fetchone()[0],
        }
    finally:
        conn.close()

    response = post_case(test_client, "request_standard_pass.json")
    assert response.status_code == 200

    conn = get_connection(settings.database_path)
    try:
        after = {
            "invoices": conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            "purchase_orders": conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0],
            "goods_receipts": conn.execute("SELECT COUNT(*) FROM goods_receipts").fetchone()[0],
        }
    finally:
        conn.close()

    assert after == before


def test_manual_audit_rejects_non_template_mode(client) -> None:
    test_client, _ = client
    request = deepcopy(load_request("request_standard_pass.json"))
    request["metadata"]["explanation_mode"] = "experimental"

    response = test_client.post("/api/mvp/manual-audit", json=request)

    assert response.status_code == 422
