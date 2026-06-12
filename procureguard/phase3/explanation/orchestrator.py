"""Fallback Orchestrator，统一决定模板或受控改写输出。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.guard import GuardResult, LoRAOutputGuard
from procureguard.phase3.explanation.renderer import DeterministicTemplateRenderer
from procureguard.phase3.explanation.rewrite_contract import (
    PROMPT_VERSION,
    RewriteRequest,
    RewriteResponse,
)
from procureguard.phase3.explanation.trace import ExplanationAuditTrail

ExplanationMode = Literal["template", "shadow", "experimental"]
RewriteProvider = Callable[[RewriteRequest], RewriteResponse | str | None]


class ExplanationResult(BaseModel):
    """解释层最终返回结果。"""

    model_config = ConfigDict(extra="forbid")

    explanation: str
    mode: ExplanationMode
    used_rewrite: bool
    audit_trail: ExplanationAuditTrail


class FallbackOrchestrator:
    """MVP 默认模板输出，受控改写必须显式开启并通过 guard。"""

    def __init__(
        self,
        renderer: DeterministicTemplateRenderer | None = None,
        guard: LoRAOutputGuard | None = None,
    ) -> None:
        self.renderer = renderer or DeterministicTemplateRenderer()
        self.guard = guard or LoRAOutputGuard()

    def explain(
        self,
        facts: CanonicalAuditFacts,
        mode: ExplanationMode = "template",
        rewrite_provider: RewriteProvider | None = None,
    ) -> ExplanationResult:
        """生成最终解释，高风险或任何失败都回退确定性模板。"""

        template = self.renderer.render(facts)
        if mode == "template":
            return self._template_result(facts, template, "mvp_template_default", mode)
        if facts.risk_level == "high":
            return self._template_result(facts, template, "high_risk_template_only", mode)
        if rewrite_provider is None:
            return self._template_result(facts, template, "lora_unavailable", mode)

        request = RewriteRequest(
            facts=facts,
            template_output=template,
            mode="experimental" if mode == "experimental" else "shadow",
        )
        try:
            response = rewrite_provider(request)
        except Exception as exc:
            return self._template_result(
                facts, template, f"model_runtime_error:{exc.__class__.__name__}", mode
            )
        normalized = self._normalize_response(response)
        if normalized is None or not normalized.raw_text.strip():
            return self._template_result(facts, template, "empty_lora_output", mode)

        guard_result = self.guard.verify(facts, normalized.raw_text)
        if not guard_result.passed or mode == "shadow":
            reason = "shadow_mode_template_default" if guard_result.passed else "guard_failed"
            return self._template_result(
                facts,
                template,
                reason,
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=guard_result,
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
            )

        trail = ExplanationAuditTrail(
            facts_hash=facts.facts_hash(),
            template_version=self.renderer.version,
            prompt_version=PROMPT_VERSION,
            model_version=normalized.model_version,
            adapter_version=normalized.adapter_version,
            raw_llm_output=normalized.raw_text,
            verifier_result=guard_result,
            fallback_reason=None,
            final_explanation=normalized.raw_text,
        )
        return ExplanationResult(
            explanation=normalized.raw_text,
            mode=mode,
            used_rewrite=True,
            audit_trail=trail,
        )

    def _template_result(
        self,
        facts: CanonicalAuditFacts,
        template: str,
        fallback_reason: str,
        mode: ExplanationMode,
        raw_llm_output: str | None = None,
        guard_result: GuardResult | None = None,
        model_version: str = "unavailable",
        adapter_version: str = "unavailable",
    ) -> ExplanationResult:
        """构造模板回退结果。"""

        trail = ExplanationAuditTrail(
            facts_hash=facts.facts_hash(),
            template_version=self.renderer.version,
            prompt_version=PROMPT_VERSION,
            model_version=model_version,
            adapter_version=adapter_version,
            raw_llm_output=raw_llm_output,
            verifier_result=guard_result
            or GuardResult(passed=True, violations=[]),
            fallback_reason=fallback_reason,
            final_explanation=template,
        )
        return ExplanationResult(
            explanation=template,
            mode=mode,
            used_rewrite=False,
            audit_trail=trail,
        )

    def _normalize_response(
        self, response: RewriteResponse | str | None
    ) -> RewriteResponse | None:
        """兼容测试和未来本地模型封装返回值。"""

        if response is None:
            return None
        if isinstance(response, RewriteResponse):
            return response
        return RewriteResponse(raw_text=response)
