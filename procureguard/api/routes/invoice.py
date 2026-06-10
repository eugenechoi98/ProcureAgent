"""发票上传、查询和轨迹接口。"""

import sqlite3
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from procureguard.api.dependencies import get_db
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.models.status import InvoiceStatus
from procureguard.repositories import AuditTraceRepository, InvoiceRepository
from procureguard.services import AgentInvoiceProcessor
from procureguard.services.mock_processor import MockInvoiceProcessor
from procureguard.storage import save_invoice_upload
from procureguard.storage.uploads import UploadValidationError

router = APIRouter()


@router.post("/invoices/upload")
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
    processing_mode: Literal["real", "mock"] = Query("real"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """上传发票文件并同步执行真实规则链，可显式切换 mock 模式。"""

    invoice_id = f"invoice_{uuid4().hex}"
    upload_dir: Path = request.app.state.settings.upload_dir
    try:
        saved = await save_invoice_upload(upload_dir, invoice_id, file)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    invoices = InvoiceRepository(conn)
    duplicate = invoices.get_invoice_by_file_hash(saved.file_hash)
    if duplicate is not None:
        saved.file_path.unlink(missing_ok=True)
        parent = saved.file_path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        raise HTTPException(
            status_code=409,
            detail=f"File already uploaded as invoice {duplicate['id']}.",
        )

    try:
        invoices.create_invoice(
            invoice_id=invoice_id,
            file_path=str(saved.file_path),
            file_hash=saved.file_hash,
        )
        if processing_mode == "mock":
            result = MockInvoiceProcessor(conn).process(invoice_id)
        else:
            report = AgentInvoiceProcessor(conn).process_extracted_invoice(
                invoice_id,
                _build_upload_extracted_fields(invoice_id),
            )
            stored = invoices.get_invoice(invoice_id)
            if stored is None:
                raise RuntimeError(f"Invoice {invoice_id} disappeared after processing.")
            result = {
                "invoice_id": invoice_id,
                "status": stored["status"],
                "risk_level": report.risk_level.value,
                "processing_mode": "real",
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "invoice_id": invoice_id,
        "status": result["status"],
        "file_hash": saved.file_hash,
        "processing_mode": result["processing_mode"],
    }


def _build_upload_extracted_fields(invoice_id: str) -> ExtractedFields:
    """在 OCR 接入前，为 API 集成测试提供稳定的已抽取字段。"""

    return ExtractedFields(
        vendor_name="Acme Office Supplies",
        invoice_number=f"INV-API-{invoice_id[-8:].upper()}",
        invoice_date="2026-06-10",
        po_number="PO-1001",
        subtotal=1100.0,
        tax=100.0,
        total_amount=1200.0,
        currency="USD",
        line_items=[
            LineItem(item="Printer Paper", qty=100, unit_price=8.0, amount=800.0),
            LineItem(item="Toner Cartridge", qty=4, unit_price=100.0, amount=400.0),
        ],
        extraction_confidence=0.96,
        extraction_model="api-placeholder-v1",
    )


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """查询单张发票。"""

    invoice = InvoiceRepository(conn).get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} was not found.")
    return invoice


@router.get("/invoices")
def list_invoices(
    status: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """查询发票列表，可按状态过滤。"""

    status_filter = None
    if status is not None:
        try:
            status_filter = InvoiceStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid invoice status: {status}") from exc
    return {"items": InvoiceRepository(conn).list_invoices(status_filter)}


@router.get("/invoices/{invoice_id}/trace")
def list_invoice_trace(
    invoice_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """查询发票审计轨迹。"""

    invoices = InvoiceRepository(conn)
    if invoices.get_invoice(invoice_id) is None:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} was not found.")
    traces = AuditTraceRepository(conn).list_traces(invoice_id)
    return {"items": traces}
