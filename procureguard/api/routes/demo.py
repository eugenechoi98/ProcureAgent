"""演示专用 API：自动使用预置 mock PO/GRN 上下文。"""

from fastapi import APIRouter, HTTPException, Request

from procureguard.productization.e2e_audit import ExecuteAuditRequest, ExecuteAuditResponse, execute_audit_pipeline


router = APIRouter(prefix="/api/demo", tags=["Demo audit"])


@router.post("/audit", response_model=ExecuteAuditResponse)
def demo_audit(payload: ExecuteAuditRequest, request: Request) -> ExecuteAuditResponse:
    """运行演示审核：用户不需要手动输入 procurement_context。"""

    try:
        normalized = payload.model_copy(update={"procurement_context": None})
        return execute_audit_pipeline(
            normalized,
            database_path=request.app.state.settings.database_path,
            explanation_rewrite_provider=request.app.state.explanation_rewrite_provider,
            demo_mode=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
