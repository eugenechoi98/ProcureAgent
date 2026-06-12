"""Phase 3H 受控解释层，对外只暴露独立解释组件。"""

from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.guard import GuardResult, LoRAOutputGuard
from procureguard.phase3.explanation.orchestrator import (
    ExplanationMode,
    ExplanationResult,
    FallbackOrchestrator,
)
from procureguard.phase3.explanation.renderer import DeterministicTemplateRenderer
from procureguard.phase3.explanation.rewrite_contract import (
    RewriteRequest,
    RewriteResponse,
    build_rewrite_prompt,
)
from procureguard.phase3.explanation.trace import ExplanationAuditTrail

__all__ = [
    "CanonicalAuditFacts",
    "DeterministicTemplateRenderer",
    "ExplanationAuditTrail",
    "ExplanationMode",
    "ExplanationResult",
    "FallbackOrchestrator",
    "GuardResult",
    "LoRAOutputGuard",
    "RewriteRequest",
    "RewriteResponse",
    "build_rewrite_prompt",
]
