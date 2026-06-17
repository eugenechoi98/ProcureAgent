"""Phase 4G 字段确认 API。"""

from fastapi import APIRouter, HTTPException

from procureguard.productization.field_confirmation import (
    FieldConfirmationRequest,
    FieldConfirmationResponse,
    confirm_fields,
)


router = APIRouter(prefix="/api/fields", tags=["Field confirmation"])


@router.post("/confirm", response_model=FieldConfirmationResponse)
def confirm_layoutlmv3_fields(payload: FieldConfirmationRequest) -> FieldConfirmationResponse:
    """把 LayoutLMv3 候选转换为人工确认后的审计事实，不运行 Phase 2。"""

    try:
        return confirm_fields(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
