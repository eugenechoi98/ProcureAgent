"""发票上传、查询和轨迹接口。"""

import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from procureguard.api.dependencies import get_db
from procureguard.models.status import InvoiceStatus
from procureguard.repositories import AuditTraceRepository, InvoiceRepository
from procureguard.services.mock_processor import MockInvoiceProcessor
from procureguard.storage import save_invoice_upload
from procureguard.storage.uploads import UploadValidationError

router = APIRouter()


@router.post("/invoices/upload")
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """上传发票文件并同步执行 mock 处理链。"""

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
        result = MockInvoiceProcessor(conn).process(invoice_id)
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
