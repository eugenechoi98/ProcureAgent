"""Phase 3H 解释路径审计追踪结构。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from procureguard.phase3.explanation.guard import GuardResult

GUARD_VERSION = "phase4h-strict-guard-v1"


class ExplanationAuditTrail(BaseModel):
    """记录解释从事实到最终文本的完整路径。"""

    model_config = ConfigDict(extra="forbid")

    facts_hash: str
    template_version: str
    template_hash: str
    prompt_version: str
    guard_version: str = GUARD_VERSION
    provider_name: str = "unavailable"
    model_version: str = "unavailable"
    adapter_version: str = "unavailable"
    latency_ms: float | None = None
    lora_candidate_hash: str | None = None
    explanation_mode_requested: str = "template"
    explanation_mode_used: str = "template"
    final_source: str = "template"
    raw_llm_output: str | None = None
    raw_lora_output_saved: bool = False
    raw_lora_output_saved_reason: str = "not_requested"
    verifier_result: GuardResult
    fallback_reason: str | None = None
    final_explanation: str = Field(min_length=1)
