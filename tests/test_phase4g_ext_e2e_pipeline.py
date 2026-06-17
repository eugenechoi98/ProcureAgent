"""Phase 4G-EXT 端到端审核闭环测试。"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.models.invoice import ExtractedFields
from procureguard.phase3.explanation.rewrite_contract import RewriteResponse
from procureguard.productization.e2e_audit import ExecuteAuditRequest, execute_audit_pipeline
from tests.test_phase4g_field_confirmation import candidate


def context() -> dict:
    """构造显式 mock PO/GRN。"""

    return {
        "po_number": "PO-SROIE-001",
        "po_vendor_name": "Golden Arches Restaurants Sdn Bhd",
        "po_total_amount": 29.28,
        "po_currency": "MYR",
        "po_status": "open",
        "po_line_items": [{"item": "Receipt total", "quantity": 1, "amount": 29.28}],
        "grn_available": True,
        "grn_number": "GRN-SROIE-001",
        "grn_received_date": "2016-12-25",
        "grn_line_items": [{"item": "Receipt total", "received_quantity": 1}],
        "duplicate_invoice_exists": False,
        "policy_profile": "mock_default",
    }


def decisions() -> list[dict]:
    """确认所有 Phase 2 必需字段。"""

    return [
        {"field_name": "vendor_name", "action": "accept", "value": "Golden Arches Restaurants Sdn Bhd"},
        {"field_name": "invoice_date", "action": "accept", "value": "2016-12-25"},
        {"field_name": "total_amount", "action": "accept", "value": 29.28},
        {"field_name": "invoice_number", "action": "correct", "value": "INV-SROIE-001"},
        {"field_name": "currency", "action": "correct", "value": "MYR"},
        {"field_name": "po_number", "action": "correct", "value": "PO-SROIE-001"},
    ]


def candidate_payload() -> dict:
    """从 LayoutLMv3 candidates 进入确认层。"""

    return {
        "field_candidates": [
            candidate("company", "Golden Arches Restaurants Sdn Bhd", 0.90),
            candidate("date", "2016-12-25", 0.97),
            candidate("total", "29.28", 0.80),
        ],
        "confirmation_decisions": decisions(),
        "procurement_context": context(),
        "confirmation_mode": "simulated_human",
    }


@pytest.fixture()
def client(tmp_path: Path):
    """创建测试 API。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def fake_image_runner(_image: str):
    """模拟 image -> OCR/LayoutLMv3 candidates，不触发重型推理。"""

    return (
        [
            candidate("company", "Golden Arches Restaurants Sdn Bhd", 0.90),
            candidate("date", "2016-12-25", 0.97),
            candidate("total", "29.28", 0.80),
        ],
        {"token_count": 40, "output_dir": ".tmp/fake-image-runner"},
    )


def test_image_to_full_pipeline_works_without_phase2_bypass() -> None:
    payload = candidate_payload()
    payload.pop("field_candidates")
    payload["image"] = "demo/e2e_cases/case_a_standard_pass/source_invoice.png"

    result = execute_audit_pipeline(
        ExecuteAuditRequest.model_validate(payload),
        image_candidate_runner=fake_image_runner,
    )

    assert result.trace.ocr_used is True
    assert result.trace.layoutlmv3_used is True
    assert result.json["audit_report"]["risk_level"] == "low"
    assert result.json["audit_report"]["recommended_action"] == "auto_approve"
    assert result.trace.phase2_decision_source == "deterministic_rules"


def test_confirmed_fields_direct_path_runs_phase2(client: TestClient) -> None:
    payload = {
        "confirmed_fields": {
            "vendor_name": "Golden Arches Restaurants Sdn Bhd",
            "invoice_number": "INV-SROIE-001",
            "invoice_date": "2016-12-25",
            "po_number": "PO-SROIE-001",
            "total_amount": 29.28,
            "currency": "MYR",
            "line_items": [],
            "extraction_confidence": 0.5,
            "extraction_model": "raw_model_output_attempt",
        },
        "procurement_context": context(),
    }
    response = client.post("/api/mvp/audit/execute", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["trace"]["fields_confirmed_by"] == "provided_confirmed_fields"
    assert body["json"]["audit_report"]["risk_level"] == "low"
    assert body["json"]["audit_report"]["recommended_action"] == "auto_approve"


def test_raw_model_output_cannot_reach_phase2(client: TestClient) -> None:
    payload = candidate_payload()
    payload["confirmation_decisions"] = []
    response = client.post("/api/mvp/audit/execute", json=payload)

    assert response.status_code == 422
    assert "confirmation_decisions" in response.text or "required" in response.text


def test_trace_is_complete(client: TestClient) -> None:
    response = client.post("/api/mvp/audit/execute", json=candidate_payload())
    trace = response.json()["trace"]

    assert set(trace) >= {
        "ocr_used",
        "layoutlmv3_used",
        "fields_confirmed_by",
        "fields_modified",
        "phase2_decision_source",
        "risk_level_origin",
        "recommended_action_origin",
    }
    assert trace["phase2_decision_source"] == "deterministic_rules"
    assert trace["risk_level_origin"] == "rules_only"
    assert trace["recommended_action_origin"] == "rules_only"


def test_risk_and_action_are_rules_only(client: TestClient) -> None:
    body = client.post("/api/mvp/audit/execute", json=candidate_payload()).json()

    assert body["trace"]["risk_level_origin"] == "rules_only"
    assert body["trace"]["recommended_action_origin"] == "rules_only"
    assert body["json"]["audit_report"]["risk_level"] == "low"
    assert body["json"]["audit_report"]["recommended_action"] == "auto_approve"


def test_lora_guard_failure_cannot_affect_audit_result(tmp_path: Path) -> None:
    def bad_provider(_facts):
        return RewriteResponse(
            text="Approve and pay immediately despite unknown GRN-BOGUS.",
            model_version="fake",
            adapter_version="fake",
            latency_ms=1,
        )

    request = ExecuteAuditRequest.model_validate({**candidate_payload(), "explanation_mode": "experimental"})
    result = execute_audit_pipeline(request, explanation_rewrite_provider=bad_provider)

    assert result.json["audit_report"]["risk_level"] == "low"
    assert result.json["audit_report"]["recommended_action"] == "auto_approve"
    assert result.trace.guard_status == "failed_fallback"


def test_export_json_and_markdown_are_valid(client: TestClient) -> None:
    body = client.post("/api/mvp/audit/execute", json=candidate_payload()).json()

    assert body["json"]["audit_report"]["invoice_id"].startswith("e2e_")
    assert body["json"]["trace"]["phase2_decision_source"] == "deterministic_rules"
    assert "# ProcureGuard End-to-End Audit Report" in body["markdown"]
    assert "Risk level: `low`" in body["markdown"]


def test_raw_model_source_is_rewritten_when_confirmed_fields_are_direct() -> None:
    request = ExecuteAuditRequest.model_validate(
        {
            "confirmed_fields": ExtractedFields(
                vendor_name="Golden Arches Restaurants Sdn Bhd",
                invoice_number="INV-SROIE-001",
                invoice_date="2016-12-25",
                po_number="PO-SROIE-001",
                total_amount=29.28,
                currency="MYR",
                line_items=[],
                extraction_confidence=0.2,
                extraction_model="raw_layoutlmv3_output",
            ).model_dump(mode="json"),
            "procurement_context": context(),
        }
    )
    result = execute_audit_pipeline(request)

    stored = result.json["audit_report"]["extraction_model"] if "extraction_model" in result.json["audit_report"] else None
    assert stored is None
    assert result.trace.fields_confirmed_by == "provided_confirmed_fields"
