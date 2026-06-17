"""Phase 4C/4D 手动审核、导出和人工复核产品入口。"""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response

from procureguard.productization.manual_audit import ManualAuditRequest, ManualAuditResponse, run_manual_audit
from procureguard.productization.e2e_audit import ExecuteAuditRequest, ExecuteAuditResponse, execute_audit_pipeline
from procureguard.productization.manual_audit_store import (
    ManualAuditRecord,
    ManualAuditStore,
    ManualReviewDecisionRequest,
    build_export,
    render_export_json,
    render_export_markdown,
)


router = APIRouter(prefix="/api/mvp", tags=["MVP manual audit"])


@router.post("/audit/execute", response_model=ExecuteAuditResponse)
def execute_mvp_audit(payload: ExecuteAuditRequest, request: Request) -> ExecuteAuditResponse:
    """运行端到端 MVP 审核：确认字段后才调用 Phase 2。"""

    try:
        return execute_audit_pipeline(
            payload,
            explanation_rewrite_provider=request.app.state.explanation_rewrite_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/manual-audit", response_model=ManualAuditResponse)
def manual_audit(payload: ManualAuditRequest, request: Request) -> ManualAuditResponse:
    """用手动字段和显式 mock 上下文运行确定性审核链。"""

    try:
        response = run_manual_audit(payload)
        _store(request).save(payload, response)
        return response
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"Manual audit request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Manual audit processing failed. No production payment decision was made.",
        ) from exc


@router.get("/manual-audit/review-queue")
def manual_review_queue(request: Request) -> dict:
    """列出当前进程中待人工复核的手动审核。"""

    items = [_review_summary(record) for record in _store(request).review_queue()]
    return {"items": items, "persistence": "process_memory_only", "payment_authority": False}


@router.post("/manual-audit/{audit_id}/review")
def submit_manual_review(
    audit_id: str,
    payload: ManualReviewDecisionRequest,
    request: Request,
) -> dict:
    """附加本地 reviewer decision，不改写确定性规则结果。"""

    try:
        record = _store(request).submit_review(audit_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _review_summary(record)


@router.get("/manual-audit/{audit_id}/export")
def export_manual_audit(
    audit_id: str,
    request: Request,
    format: Literal["json", "markdown"] = Query(default="json"),
) -> Response:
    """导出机器可读 JSON 或稳定 Markdown。"""

    record = _store(request).get(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Manual audit {audit_id} was not found.")
    if format == "json":
        return Response(
            content=render_export_json(record),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{audit_id}.json"'},
        )
    return Response(
        content=render_export_markdown(record),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{audit_id}.md"'},
    )


def _store(request: Request) -> ManualAuditStore:
    """读取应用级本地 MVP store。"""

    return request.app.state.manual_audit_store


def _review_summary(record: ManualAuditRecord) -> dict:
    """返回 review UX 需要的状态，不复制完整导出。"""

    export = build_export(record)
    return {
        "audit_id": export.audit_id,
        "trace_id": export.trace_id,
        "risk_level": export.risk_level,
        "recommended_action": export.recommended_action,
        "review_status": export.review_status,
        "review_decision": export.review_decision,
        "reviewer_note": export.reviewer_note,
        "reviewed_at": export.reviewed_at,
        "source_labels": export.source_labels,
        "fallback_status": export.fallback_status,
        "payment_authority": False,
        "deterministic_result_unchanged": True,
    }
