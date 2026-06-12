"""Fallback Orchestrator，统一决定模板或受控改写输出。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

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
RewriteProvider = Callable[[RewriteRequest], Any]


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

        try:
            request = RewriteRequest(
                facts=facts,
                template_output=template,
                mode="experimental" if mode == "experimental" else "shadow",
            )
            response = rewrite_provider(request)
        except ValidationError:
            return self._template_result(
                facts,
                template,
                "rewrite_parse_error",
                mode,
                guard_result=self._failed_guard("rewrite_parse_error"),
            )
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                "model_runtime_error",
                mode,
                guard_result=self._failed_guard(
                    f"model_runtime_error:{exc.__class__.__name__}"
                ),
            )

        raw_output = self._capture_raw_output(response)
        if response is None or (isinstance(response, str) and response == ""):
            return self._template_result(
                facts,
                template,
                "empty_lora_output",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard("empty_lora_output"),
            )
        try:
            normalized = self._normalize_response(response)
        except ValidationError:
            return self._template_result(
                facts,
                template,
                "rewrite_parse_error",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard("rewrite_parse_error"),
            )
        except (TypeError, ValueError):
            return self._template_result(
                facts,
                template,
                "invalid_lora_output",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard("invalid_lora_output"),
            )
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                "rewrite_parse_error",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard(
                    f"rewrite_parse_error:{exc.__class__.__name__}"
                ),
            )
        if not normalized.raw_text.strip():
            return self._template_result(
                facts,
                template,
                "empty_lora_output",
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=self._failed_guard("empty_lora_output"),
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
            )

        try:
            guard_result = self.guard.verify(facts, normalized.raw_text)
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                "guard_parse_error",
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=self._failed_guard(
                    f"guard_parse_error:{exc.__class__.__name__}"
                ),
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
            )
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
            or self._failed_guard(fallback_reason),
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
        self, response: Any
    ) -> RewriteResponse:
        """只接受字符串、RewriteResponse 或可校验的契约字典。"""

        if isinstance(response, RewriteResponse):
            return response
        if isinstance(response, str):
            return RewriteResponse(raw_text=response)
        if isinstance(response, Mapping):
            return RewriteResponse.model_validate(dict(response))
        raise TypeError("LoRA 输出必须是字符串或 RewriteResponse 契约")

    def _capture_raw_output(self, response: Any) -> str | None:
        """尽可能保留非法返回值，同时保证审计转换本身不抛异常。"""

        if response is None:
            return None
        if isinstance(response, RewriteResponse):
            return response.raw_text
        if isinstance(response, str):
            return response
        try:
            return json.dumps(response, ensure_ascii=False, default=repr)
        except Exception:
            try:
                return repr(response)
            except Exception:
                return f"<unrepresentable:{type(response).__name__}>"

    def _failed_guard(self, violation: str) -> GuardResult:
        """未进入或未完成 guard 时也留下失败审计记录。"""

        return GuardResult(passed=False, violations=[violation])
