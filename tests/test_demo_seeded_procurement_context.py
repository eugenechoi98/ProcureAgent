"""演示 mock PO/GRN 自动查询路径测试。"""

from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from tests.test_phase4g_ext_e2e_pipeline import context


@pytest.fixture()
def client(tmp_path: Path):
    """创建已初始化 demo seed 的测试 API。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client, settings


def confirmed_fields(
    *,
    vendor_name: str,
    total_amount: float,
    invoice_number: str | None = None,
) -> dict:
    """构造直接确认后的发票字段。"""

    return {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "invoice_date": "2026-01-15",
        "total_amount": total_amount,
        "currency": "MYR",
        "line_items": [],
        "extraction_confidence": 1.0,
        "extraction_model": "provided_by_demo_test",
    }


def post_auto_context(test_client: TestClient, fields: dict, path: str = "/api/mvp/audit/execute"):
    """提交不含 procurement_context 的演示请求。"""

    return test_client.post(path, json={"confirmed_fields": fields})


def assert_demo_labels(body: dict) -> None:
    """检查演示来源标签。"""

    labels = body["source_labels"]
    assert labels["demo_mode"] is True
    assert labels["context_source"] == "pre_seeded_mock_po_grn"
    assert labels["payment_authority"] is False
    assert labels["mock_data_notice"] == (
        "PO/GRN data is pre-seeded demo data, not real enterprise records"
    )
    assert body["json"]["audit_report"]["source_labels"] == labels


def test_seed_demo_data_script_runs_cleanly(tmp_path: Path) -> None:
    """seed 脚本可幂等初始化演示采购数据。"""

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/seed_demo_data.py",
            "--database-path",
            str(tmp_path / "demo.sqlite3"),
            "--reset",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert '"ready": true' in completed.stdout
    assert "demo_case_a_standard_pass" in completed.stdout


def test_case_a_auto_context_standard_pass(client) -> None:
    """案例 A：invoice_number 精确命中，三单匹配通过。"""

    test_client, _ = client
    response = post_auto_context(
        test_client,
        confirmed_fields(
            vendor_name="OJC MARKETING SDN BHD",
            invoice_number="PEGIV-1030765",
            total_amount=193.00,
        ),
    )
    body = response.json()
    report = body["json"]["audit_report"]

    assert response.status_code == 200
    assert report["po_match"] is True
    assert report["goods_receipt_match"] is True
    assert report["risk_level"] == "low"
    assert report["recommended_action"] == "auto_approve"
    assert_demo_labels(body)


def test_case_b_auto_context_amount_mismatch(client) -> None:
    """案例 B：vendor keyword 模糊命中，金额差异进入人工审核。"""

    test_client, _ = client
    response = post_auto_context(
        test_client,
        confirmed_fields(
            vendor_name="Perniagaan Zheng Hui",
            total_amount=436.20,
        ),
    )
    body = response.json()
    report = body["json"]["audit_report"]

    assert response.status_code == 200
    assert report["po_match"] is False
    assert report["risk_level"] == "medium"
    assert report["recommended_action"] == "request_human_approval"
    assert {
        "field": "total_amount",
        "invoice_value": 436.20,
        "expected": 400.00,
    } in report["mismatches"]
    assert_demo_labels(body)


def test_case_c_auto_context_duplicate_rejects(client) -> None:
    """案例 C：invoice_number 精确命中，并触发重复发票拒绝。"""

    test_client, _ = client
    response = post_auto_context(
        test_client,
        confirmed_fields(
            vendor_name="OJC MARKETING SDN BHD",
            invoice_number="PEGIV-1030531",
            total_amount=170.00,
        ),
    )
    body = response.json()
    report = body["json"]["audit_report"]

    assert response.status_code == 200
    assert report["risk_level"] == "high"
    assert report["recommended_action"] == "reject"
    assert "duplicate_invoice" in report["policy_flags"]
    assert any(item["field"] == "invoice_number" for item in report["mismatches"])
    assert_demo_labels(body)


def test_missing_demo_context_returns_no_po_found(client) -> None:
    """未命中预置 PO 时 fail closed 到人工审核。"""

    test_client, _ = client
    response = post_auto_context(
        test_client,
        confirmed_fields(
            vendor_name="UNKNOWN SUPPLIER",
            invoice_number="INV-NOT-SEEDED",
            total_amount=99.00,
        ),
    )
    body = response.json()
    report = body["json"]["audit_report"]

    assert response.status_code == 200
    assert body["source_labels"]["context_source"] == "no_po_found"
    assert body["trace"]["procurement_context_source"] == "no_po_found"
    assert report["context_resolution"]["status"] == "no_po_found"
    assert report["risk_level"] == "medium"
    assert report["recommended_action"] == "request_human_approval"


def test_explicit_context_keeps_backward_compatible_path(client) -> None:
    """显式传入 procurement_context 时不使用 demo seed。"""

    test_client, _ = client
    payload = {
        "confirmed_fields": confirmed_fields(
            vendor_name="Golden Arches Restaurants Sdn Bhd",
            invoice_number="INV-SROIE-001",
            total_amount=29.28,
        )
        | {"po_number": "PO-SROIE-001"},
        "procurement_context": context(),
    }
    response = test_client.post("/api/mvp/audit/execute", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["source_labels"]["demo_mode"] is False
    assert body["source_labels"]["context_source"] == "explicit_mock_context"
    assert body["json"]["audit_report"]["risk_level"] == "low"


def test_demo_audit_endpoint_marks_demo_response(client) -> None:
    """演示专用接口返回 demo endpoint 标识。"""

    test_client, _ = client
    response = post_auto_context(
        test_client,
        confirmed_fields(
            vendor_name="OJC",
            invoice_number="PEGIV-1030765",
            total_amount=193.00,
        ),
        path="/api/demo/audit",
    )
    body = response.json()

    assert response.status_code == 200
    assert body["json"]["context_source"] == "demo_mock_database"
    assert body["source_labels"]["demo_mode"] is True
