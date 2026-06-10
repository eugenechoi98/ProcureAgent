"""人工审核队列接口。"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from procureguard.api.dependencies import get_db
from procureguard.repositories import ReviewRepository

router = APIRouter()


class ReviewDecisionRequest(BaseModel):
    """人工审核决定请求体。"""

    action: str
    comment: str | None = None


@router.get("/review/queue")
def list_review_queue(
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """查询 pending 人工审核队列。"""

    return {"items": ReviewRepository(conn).list_pending_reviews()}


@router.post("/review/{review_id}/decision")
def submit_review_decision(
    review_id: str,
    request: ReviewDecisionRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """提交人工审核决定。"""

    repo = ReviewRepository(conn)
    try:
        return repo.submit_decision(
            review_id=review_id,
            action=request.action,
            comment=request.comment,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
