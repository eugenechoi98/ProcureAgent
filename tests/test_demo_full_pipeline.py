"""POST /api/demo/full_pipeline 全链路 demo 接口测试。"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from procureguard.api.main import create_app
from procureguard.config import Settings
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.productization import demo_full_pipeline
from procureguard.productization.demo_full_pipeline import (
    DemoFullPipelineError,
    LayoutLMv3ExtractionResult,
)


@pytest.fixture()
def client(tmp_path: Path):
    """创建带 demo seed 数据的测试 API。"""

    settings = Settings(database_path=tmp_path / "app.sqlite3", upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def fake_extraction(
    *,
    vendor_name: str,
    total_amount: float,
    invoice_number: str | None = None,
) -> LayoutLMv3ExtractionResult:
    """构造已通过真实边界返回的数据形状，测试不运行重型模型。"""

    fields = ExtractedFields(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        invoice_date="2019-01-15",
        total_amount=total_amount,
        currency="MYR",
        line_items=[
            LineItem(
                item="Receipt total",
                qty=1,
                unit_price=total_amount,
                amount=total_amount,
            )
        ],
        extraction_confidence=0.91,
        extraction_model="live_layoutlmv3_full_pipeline",
    )
    return LayoutLMv3ExtractionResult(
        field_candidates={
            "invoice_number": invoice_number,
            "vendor_name": vendor_name,
            "total_amount": total_amount,
            "currency": "MYR",
            "requires_human_confirmation": True,
            "source": "live_layoutlmv3",
        },
        extracted_fields=fields,
        trace={"source": "live_layoutlmv3", "token_count": 42},
    )


def post_image(client: TestClient):
    """上传一张测试图片占位，实际 OCR 边界由 monkeypatch 控制。"""

    return client.post(
        "/api/demo/full_pipeline",
        files={"file": ("invoice.jpg", b"fake-image-bytes", "image/jpeg")},
    )


def test_openapi_exposes_full_pipeline(client: TestClient) -> None:
    """Swagger/OpenAPI 能看到新接口。"""

    schema = client.get("/openapi.json").json()

    assert "/api/demo/full_pipeline" in schema["paths"]


def test_success_path_runs_full_pipeline(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """案例 A：真实抽取边界返回 OJC 发票后，自动匹配 PO/GRN 并通过。"""

    monkeypatch.setattr(
        demo_full_pipeline,
        "run_layoutlmv3",
        lambda **_: fake_extraction(
            vendor_name="OJC MARKETING SDN BHD",
            invoice_number="PEGIV-1030765",
            total_amount=193.00,
        ),
    )

    response = post_image(client)
    body = response.json()

    assert response.status_code == 200
    assert body["demo_mode"] is True
    assert body["context_source"] == "full_pipeline_demo_mock_db"
    assert body["live_layoutlmv3_used"] is True
    assert body["procurement_context"]["po_number"] == "PO-DEMO-001"
    assert body["audit"]["risk_level"] == "low"
    assert body["audit"]["recommended_action"] == "auto_approve"
    assert body["audit"]["raw"]["source_labels"]["risk_decision_source"] == "deterministic_rules"
    assert body["explanation"]


def test_ocr_failure_returns_error_without_fake_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LayoutLMv3 失败时直接报错，不生成 unknown/mock OCR 字段。"""

    def fail_layoutlmv3(**_):
        raise DemoFullPipelineError(
            "layoutlmv3_failed",
            "Fine-tuned LayoutLMv3 checkpoint is unavailable.",
            {"failure_code": "missing_checkpoint"},
        )

    monkeypatch.setattr(demo_full_pipeline, "run_layoutlmv3", fail_layoutlmv3)

    response = post_image(client)
    body = response.json()

    assert response.status_code == 503
    assert body["detail"]["code"] == "layoutlmv3_failed"
    assert body["detail"]["failure_code"] == "missing_checkpoint"
    assert "field_candidates" not in body


def test_no_po_found_path_returns_context_hint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未命中 demo PO/GRN 时返回 no_po_found，并仍由规则链给出人工审核。"""

    monkeypatch.setattr(
        demo_full_pipeline,
        "run_layoutlmv3",
        lambda **_: fake_extraction(
            vendor_name="UNKNOWN SUPPLIER",
            invoice_number="INV-NOT-SEEDED",
            total_amount=99.00,
        ),
    )

    response = post_image(client)
    body = response.json()

    assert response.status_code == 200
    assert body["procurement_context"]["status"] == "no_po_found"
    assert body["procurement_context"]["risk_hint"] == "medium"
    assert body["audit"]["risk_level"] == "medium"
    assert body["audit"]["recommended_action"] == "request_human_approval"
    assert body["audit"]["raw"]["context_resolution"]["status"] == "no_po_found"


def test_duplicate_detection_path_rejects(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """案例 C：重复发票命中后由 Phase 2 规则拒绝。"""

    monkeypatch.setattr(
        demo_full_pipeline,
        "run_layoutlmv3",
        lambda **_: fake_extraction(
            vendor_name="OJC MARKETING SDN BHD",
            invoice_number="PEGIV-1030531",
            total_amount=170.00,
        ),
    )

    response = post_image(client)
    body = response.json()

    assert response.status_code == 200
    assert body["procurement_context"]["po_number"] == "PO-DEMO-003"
    assert body["procurement_context"]["duplicate_invoice_exists"] is True
    assert body["audit"]["risk_level"] == "high"
    assert body["audit"]["recommended_action"] == "reject"
    assert "duplicate_invoice" in body["audit"]["raw"]["policy_flags"]


def test_amount_mismatch_uses_vendor_keyword_lookup(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """案例 B：供应商关键词命中 PO-DEMO-002，金额差异进入人工审核。"""

    monkeypatch.setattr(
        demo_full_pipeline,
        "run_layoutlmv3",
        lambda **_: fake_extraction(
            vendor_name="PERNIAGAAN ZHENG HUI",
            invoice_number="CS00022258",
            total_amount=436.20,
        ),
    )

    response = post_image(client)
    body = response.json()

    assert response.status_code == 200
    assert body["procurement_context"]["po_number"] == "PO-DEMO-002"
    assert body["audit"]["risk_level"] == "medium"
    assert body["audit"]["recommended_action"] == "request_human_approval"
    assert {
        "field": "total_amount",
        "invoice_value": 436.20,
        "expected": 400.00,
    } in body["audit"]["raw"]["mismatches"]
