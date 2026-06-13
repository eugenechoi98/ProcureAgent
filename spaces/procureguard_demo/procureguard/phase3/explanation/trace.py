"""Phase 3H 解释路径审计追踪结构。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from procureguard.phase3.explanation.guard import GuardResult


class ExplanationAuditTrail(BaseModel):
    """记录解释从事实到最终文本的完整路径。"""

    model_config = ConfigDict(extra="forbid")

    facts_hash: str
    template_version: str
    prompt_version: str
    model_version: str = "unavailable"
    adapter_version: str = "unavailable"
    raw_llm_output: str | None = None
    verifier_result: GuardResult
    fallback_reason: str | None = None
    final_explanation: str = Field(min_length=1)
