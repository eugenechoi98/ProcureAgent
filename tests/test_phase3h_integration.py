"""Phase 3H 受控解释层与真实审核输出的端到端测试。"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from procureguard.api.main import create_app
from procureguard.api.routes import invoice as invoice_route
from procureguard.config import Settings
from procureguard.db import initialize_database, seed_mock_data, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.phase3.explanation import RewriteRequest, RewriteResponse
from procureguard.repositories import AuditTraceRepository, InvoiceRepository
from procureguard.services import AgentInvoiceProcessor


def _settings(tmp_path, name: str = "integration") -> Settings:
    return Settings(
        database_path=tmp_path / f"{name}.sqlite3",
        upload_dir=tmp_path / f"{name}-uploads",
    )


def _client(tmp_path, provider=None, name: str = "integration") -> Iterator[TestClient]:
    app = create_app(
        _settings(tmp_path, name),
        explanation_rewrite_provider=provider,
    )
    return TestClient(app)


def _upload(
    client: TestClient,
    *,
    mode: str = "template",
    content: bytes = b"%PDF phase3h integration",
):
    return client.post(
        "/invoices/upload",
        params={"explanation_mode": mode},
        files={"file": ("invoice.pdf", content, "application/pdf")},
    )


def _pass_provider(request: RewriteRequest) -> RewriteResponse:
    return RewriteResponse(
        raw_text=request.template_output,
        model_version="fake-integration-model",
        adapter_version="fake-integration-adapter",
    )


def _unsafe_provider(request: RewriteRequest) -> RewriteResponse:
    return RewriteResponse(
        raw_text=request.template_output.replace(
            request.facts.invoice_number or "未提供（缺失）",
            "INV-UNSUPPORTED-999",
        ),
        model_version="fake-integration-model",
        adapter_version="fake-integration-adapter",
    )


def _runtime_error_provider(_request: RewriteRequest):
    raise RuntimeError("fake provider failed")


def _build_clean_fields(invoice_number: str = "INV-INTEGRATION-001"):
    return ExtractedFields(
        vendor_name="Acme Office Supplies",
        invoice_number=invoice_number,
        invoice_date="2026-06-10",
        po_number="PO-1001",
        total_amount=1200.0,
        currency="USD",
        line_items=[
            LineItem(item="Printer Paper", qty=100),
            LineItem(item="Toner Cartridge", qty=4),
        ],
        extraction_confidence=0.99,
        extraction_model="phase3h-test",
    )


def test_default_api_path_is_template_and_backward_compatible(tmp_path):
    with _client(tmp_path) as client:
        response = _upload(client)
        payload = response.json()
        invoice = client.get(f"/invoices/{payload['invoice_id']}").json()
        explanation = payload["explanation"]

        assert response.status_code == 200
        assert {"invoice_id", "status", "file_hash", "processing_mode"} <= payload.keys()
        assert explanation["explanation_source"] == "template"
        assert explanation["explanation_mode"] == "template"
        assert explanation["used_rewrite"] is False
        assert explanation["fallback_reason"] == "mvp_template_default"
        assert explanation["raw_llm_output"] is None
        assert invoice["audit_report"]["explanation"] == explanation
        assert invoice["audit_report"]["risk_level"] == "low"
        assert invoice["audit_report"]["recommended_action"] == "auto_approve"
        assert explanation["anomaly_types"] == []
        assert [item["step_name"] for item in client.get(
            f"/invoices/{payload['invoice_id']}/trace"
        ).json()["items"]] == [
            "extraction",
            "validation",
            "agent_call",
            "risk_calc",
        ]


def test_same_completed_audit_facts_produce_stable_text_and_hash():
    conn = get_connection(":memory:")
    try:
        initialize_database(conn)
        seed_mock_data(conn)
        seed_policy_documents(conn)
        fields = _build_clean_fields()
        reports = []
        for invoice_id in ("stable_invoice",):
            InvoiceRepository(conn).create_invoice(
                invoice_id, f"{invoice_id}.pdf", f"hash-{invoice_id}"
            )
            reports.append(
                AgentInvoiceProcessor(conn).process_extracted_invoice(
                    invoice_id, fields
                )
            )
        stored = InvoiceRepository(conn).get_invoice("stable_invoice")

        assert reports[0].explanation.explanation_text == stored["audit_report"][
            "explanation"
        ]["explanation_text"]
        assert reports[0].explanation.facts_hash == stored["audit_report"][
            "explanation"
        ]["facts_hash"]
    finally:
        conn.close()


def test_phase2_outputs_are_preserved_after_explanation():
    conn = get_connection(":memory:")
    try:
        initialize_database(conn)
        seed_mock_data(conn)
        seed_policy_documents(conn)
        InvoiceRepository(conn).create_invoice(
            "phase2_invariant", "phase2.pdf", "hash-phase2-invariant"
        )
        fields = ExtractedFields(
            vendor_name="Northwind Industrial",
            invoice_number="INV-INVARIANT-001",
            invoice_date="2026-06-10",
            po_number="PO-2001",
            total_amount=12500.0,
            currency="USD",
            line_items=[
                LineItem(item="Safety Gloves", qty=500),
                LineItem(item="Machine Parts", qty=10),
            ],
            extraction_confidence=0.98,
            extraction_model="phase3h-test",
        )

        report = AgentInvoiceProcessor(conn).process_extracted_invoice(
            "phase2_invariant", fields
        )
        stored = InvoiceRepository(conn).get_invoice("phase2_invariant")
        explanation = report.explanation

        assert stored["validation_result"]["po_match"] is True
        assert stored["validation_result"]["grn_match"] is False
        assert stored["validation_result"]["amount_match"] is True
        assert stored["validation_result"]["duplicate_check"] is True
        assert report.risk_level.value == "medium"
        assert report.recommended_action.value == "request_human_approval"
        assert explanation.anomaly_types == [
            "quantity_mismatch",
            "high_value_approval_required",
        ]
        assert explanation.evidence == [
            item.model_dump(mode="json") for item in report.evidence
        ]
        assert explanation.missing_fields == []
        assert [trace["step_name"] for trace in AuditTraceRepository(conn).list_traces(
            "phase2_invariant"
        )] == ["extraction", "validation", "agent_call", "risk_calc"]
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("mode", "provider", "source", "fallback", "guard_passed"),
    [
        ("shadow", _pass_provider, "template", "shadow_mode_template_default", True),
        ("experimental", _pass_provider, "controlled_rewrite", None, True),
        ("experimental", _unsafe_provider, "template", "guard_failed", False),
        ("experimental", None, "template", "lora_unavailable", False),
        ("experimental", lambda _request: "", "template", "empty_lora_output", False),
        ("experimental", lambda _request: 123, "template", "invalid_lora_output", False),
        ("experimental", _runtime_error_provider, "template", "model_runtime_error", False),
        (
            "experimental",
            lambda _request: {"raw_text": None},
            "template",
            "rewrite_parse_error",
            False,
        ),
    ],
)
def test_api_modes_fail_closed_without_changing_phase2(
    tmp_path, mode, provider, source, fallback, guard_passed
):
    with _client(tmp_path, provider, name=f"mode-{fallback or 'pass'}") as client:
        response = _upload(
            client,
            mode=mode,
            content=f"%PDF {mode} {fallback}".encode(),
        )
        payload = response.json()
        explanation = payload["explanation"]
        invoice = client.get(f"/invoices/{payload['invoice_id']}").json()

        assert response.status_code == 200
        assert explanation["explanation_source"] == source
        assert explanation["fallback_reason"] == fallback
        assert explanation["guard_passed"] is guard_passed
        assert invoice["audit_report"]["risk_level"] == "low"
        assert invoice["audit_report"]["recommended_action"] == "auto_approve"
        assert explanation["anomaly_types"] == []
        if provider in {_pass_provider, _unsafe_provider}:
            assert explanation["raw_llm_output"]
            assert explanation["model_version"] == "fake-integration-model"
            assert explanation["adapter_version"] == "fake-integration-adapter"
        if fallback == "guard_failed":
            assert explanation["guard_violations"]


def test_high_risk_api_forces_template_without_calling_provider(
    tmp_path, monkeypatch
):
    called = False

    def forbidden_provider(_request):
        nonlocal called
        called = True
        raise AssertionError("高风险不应调用 provider")

    monkeypatch.setattr(
        invoice_route,
        "_build_upload_extracted_fields",
        lambda _invoice_id: _build_clean_fields("INV-DUP-001"),
    )
    with _client(tmp_path, forbidden_provider, name="high-risk") as client:
        response = _upload(
            client,
            mode="experimental",
            content=b"%PDF high risk explanation fallback",
        )
        payload = response.json()
        invoice = client.get(f"/invoices/{payload['invoice_id']}").json()

        assert response.status_code == 200
        assert called is False
        assert payload["explanation"]["explanation_source"] == "template"
        assert payload["explanation"]["fallback_reason"] == "high_risk_template_only"
        assert invoice["audit_report"]["risk_level"] == "high"
        assert invoice["audit_report"]["recommended_action"] == "reject"
        assert payload["explanation"]["anomaly_types"] == ["duplicate_invoice"]
