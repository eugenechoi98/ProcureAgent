"""演示专用 API：自动使用预置 mock PO/GRN 上下文。"""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from procureguard.productization.e2e_audit import ExecuteAuditRequest, ExecuteAuditResponse, execute_audit_pipeline
from procureguard.productization.demo_full_pipeline import (
    DemoFullPipelineError,
    DemoFullPipelineResponse,
    run_demo_full_pipeline,
)


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


@router.post("/full_pipeline", response_model=DemoFullPipelineResponse)
async def demo_full_pipeline(
    request: Request,
    file: UploadFile = File(...),
) -> DemoFullPipelineResponse:
    """上传单张发票图片，真实执行 LayoutLMv3 -> demo PO/GRN -> Phase 2。"""

    image_bytes = await file.read()
    try:
        return run_demo_full_pipeline(
            image_bytes=image_bytes,
            filename=file.filename,
            database_path=request.app.state.settings.database_path,
            explanation_rewrite_provider=request.app.state.explanation_rewrite_provider,
        )
    except DemoFullPipelineError as exc:
        raise HTTPException(
            status_code=503 if exc.code == "layoutlmv3_failed" else 400,
            detail={
                "code": exc.code,
                "message": exc.message,
                **exc.detail,
            },
        ) from exc
