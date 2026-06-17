"""Phase 4G 字段确认层与确定性审核接入边界测试。"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.models.invoice import ExtractedFields
from procureguard.productization.field_confirmation import (
    ConfirmedAuditInput,
    FieldConfirmationRequest,
    confirm_fields,
    confirmed_audit_input_to_extracted_fields,
)


def candidate(field: str, value, confidence: float = 0.9) -> dict:
    """构造 LayoutLMv3 字段候选。"""

    return {
        "field_name": field,
        "predicted_value": value,
        "confidence": confidence,
        "token_spans": [{"start": 0, "end": 0}],
        "bbox_list": [[0, 0, 100, 100]],
        "source": "live_layoutlmv3",
        "requires_human_confirmation": True,
        "warning": None,
        "failure_reason": None,
    }


def confirmed_payload() -> dict:
    """生成完整确认请求。"""

    return {
        "trace_id": "phase4g-test",
        "confirmation_mode": "simulated_human",
        "candidates": [
            candidate("company", "Golden Arches Restaurants Sdn Bhd", 0.99),
            candidate("date", "2016-12-25", 0.98),
            candidate("total", "29.28", 0.96),
        ],
        "decisions": [
            {"field_name": "vendor_name", "action": "accept", "value": "Golden Arches Restaurants Sdn Bhd"},
            {"field_name": "invoice_date", "action": "accept", "value": "2016-12-25"},
            {"field_name": "total_amount", "action": "accept", "value": 29.28},
            {"field_name": "invoice_number", "action": "correct", "value": "INV-SROIE-001"},
            {"field_name": "currency", "action": "correct", "value": "MYR"},
            {"field_name": "po_number", "action": "correct", "value": "PO-SROIE-001"},
        ],
    }


@pytest.fixture()
def client(tmp_path: Path):
    """创建 API 测试客户端。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_model_output_cannot_bypass_confirmation() -> None:
    payload = confirmed_payload()
    payload["decisions"] = []

    with pytest.raises(ValueError, match="cannot bypass confirmation"):
        FieldConfirmationRequest.model_validate(payload)


def test_confirmed_fields_required_for_phase2_input() -> None:
    response = confirm_fields(FieldConfirmationRequest.model_validate(confirmed_payload()))

    assert response.status == "confirmed"
    assert response.audit_input is not None
    extracted = confirmed_audit_input_to_extracted_fields(response.audit_input)
    assert isinstance(extracted, ExtractedFields)
    assert extracted.extraction_model == "confirmed_fields_from_layoutlmv3_candidates"


def test_rejected_fields_are_not_used_and_make_required_field_missing() -> None:
    payload = confirmed_payload()
    payload["decisions"][2] = {"field_name": "total_amount", "action": "reject"}
    response = confirm_fields(FieldConfirmationRequest.model_validate(payload))

    assert response.status == "incomplete"
    assert "total_amount" in response.rejected_fields
    assert "total_amount" in response.missing_fields
    assert response.audit_input is None


def test_critical_fields_require_confirmation_even_with_high_confidence() -> None:
    payload = confirmed_payload()
    payload["decisions"] = [
        decision for decision in payload["decisions"] if decision["field_name"] != "vendor_name"
    ]
    response = confirm_fields(FieldConfirmationRequest.model_validate(payload))
    vendor = [item for item in response.governance if item.canonical_field == "vendor_name"][0]

    assert response.status == "incomplete"
    assert vendor.status == "must_confirm"
    assert vendor.used_for_audit is False
    assert "vendor_name" in response.missing_fields


def test_confirmation_layer_preserves_traceability() -> None:
    response = confirm_fields(FieldConfirmationRequest.model_validate(confirmed_payload()))
    total = [item for item in response.governance if item.canonical_field == "total_amount"][0]

    assert total.source == "live_layoutlmv3"
    assert total.confidence == 0.96
    assert total.requires_human_confirmation is True
    assert total.used_for_audit is True


def test_risk_and_action_are_not_generated_by_confirmation_layer(client: TestClient) -> None:
    response = client.post("/api/fields/confirm", json=confirmed_payload())
    payload = response.json()

    assert response.status_code == 200
    assert payload["phase2_invoked"] is False
    assert payload["risk_level_generated"] is False
    assert payload["recommended_action_generated"] is False
    assert "risk_level" not in payload
    assert "recommended_action" not in payload


def test_layoutlmv3_cannot_directly_trigger_audit(client: TestClient) -> None:
    payload = confirmed_payload()
    payload.pop("decisions")
    response = client.post("/api/fields/confirm", json=payload)

    assert response.status_code == 422
    assert "decisions" in response.text


def test_ocr_failure_does_not_break_confirmation_when_human_supplies_missing_fields() -> None:
    payload = confirmed_payload()
    payload["candidates"] = []
    response = confirm_fields(FieldConfirmationRequest.model_validate(payload))

    assert response.status == "confirmed"
    assert response.audit_input is not None
    assert all(item.source == "human_supplied_or_missing" for item in response.governance)


def test_no_model_influence_on_audit_decision_contract() -> None:
    response = confirm_fields(FieldConfirmationRequest.model_validate(confirmed_payload()))

    assert response.audit_input is not None
    assert response.audit_input.risk_decision_source == "deterministic_rules_only"
    assert response.audit_input.raw_model_bypass_allowed is False


def test_invalid_confirmed_input_cannot_be_constructed_for_bypass() -> None:
    with pytest.raises(ValueError):
        ConfirmedAuditInput(
            confirmed_fields=ExtractedFields(
                vendor_name="A",
                invoice_number="I",
                invoice_date="2026-06-17",
                total_amount=1.0,
                currency="USD",
                po_number="PO",
                line_items=[],
                extraction_confidence=1.0,
                extraction_model="raw_model_output",
            ),
            confirmation_trace=[],
            raw_model_bypass_allowed=True,
        )
