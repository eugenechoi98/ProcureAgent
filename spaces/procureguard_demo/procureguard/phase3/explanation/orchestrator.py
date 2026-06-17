"""Fallback Orchestrator，统一决定模板或受控改写输出。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
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

ExplanationMode = Literal[
    "template", "shadow", "experimental", "shadow_lora", "guarded_lora"
]
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
        template_hash = self._text_hash(template)
        if mode == "template":
            return self._template_result(
                facts, template, template_hash, "mvp_template_default", mode
            )
        if facts.risk_level == "high":
            return self._template_result(
                facts, template, template_hash, "high_risk_template_only", mode
            )
        if rewrite_provider is None:
            return self._template_result(
                facts,
                template,
                template_hash,
                self._provider_unavailable_reason(mode),
                mode,
            )

        try:
            request = RewriteRequest(
                facts=facts,
                template_output=template,
                mode=self._rewrite_request_mode(mode),
            )
            response = rewrite_provider(request)
        except ValidationError:
            return self._template_result(
                facts,
                template,
                template_hash,
                "rewrite_parse_error",
                mode,
                guard_result=self._failed_guard("rewrite_parse_error"),
            )
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                template_hash,
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
                template_hash,
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
                template_hash,
                "rewrite_parse_error",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard("rewrite_parse_error"),
            )
        except (TypeError, ValueError):
            return self._template_result(
                facts,
                template,
                template_hash,
                "invalid_lora_output",
                mode,
                raw_llm_output=raw_output,
                guard_result=self._failed_guard("invalid_lora_output"),
            )
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                template_hash,
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
                template_hash,
                "empty_lora_output",
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=self._failed_guard("empty_lora_output"),
                provider_name=normalized.provider_name,
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
                latency_ms=normalized.latency_ms,
            )

        try:
            guard_result = self.guard.verify(facts, normalized.raw_text)
        except Exception as exc:
            return self._template_result(
                facts,
                template,
                template_hash,
                "guard_parse_error",
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=self._failed_guard(
                    f"guard_parse_error:{exc.__class__.__name__}"
                ),
                provider_name=normalized.provider_name,
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
                latency_ms=normalized.latency_ms,
            )
        if not guard_result.passed or self._is_shadow_mode(mode):
            reason = "shadow_mode_template_default" if guard_result.passed else "guard_failed"
            return self._template_result(
                facts,
                template,
                template_hash,
                reason,
                mode,
                raw_llm_output=normalized.raw_text,
                guard_result=guard_result,
                provider_name=normalized.provider_name,
                model_version=normalized.model_version,
                adapter_version=normalized.adapter_version,
                latency_ms=normalized.latency_ms,
            )

        trail = ExplanationAuditTrail(
            facts_hash=facts.facts_hash(),
            template_version=self.renderer.version,
            template_hash=template_hash,
            prompt_version=PROMPT_VERSION,
            provider_name=normalized.provider_name,
            model_version=normalized.model_version,
            adapter_version=normalized.adapter_version,
            latency_ms=normalized.latency_ms,
            lora_candidate_hash=self._text_hash(normalized.raw_text),
            explanation_mode_requested=mode,
            explanation_mode_used=mode,
            final_source="lora",
            raw_llm_output=normalized.raw_text,
            raw_lora_output_saved=True,
            raw_lora_output_saved_reason="local_trace_for_guard_audit",
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
        template_hash: str,
        fallback_reason: str,
        mode: ExplanationMode,
        raw_llm_output: str | None = None,
        guard_result: GuardResult | None = None,
        provider_name: str = "unavailable",
        model_version: str = "unavailable",
        adapter_version: str = "unavailable",
        latency_ms: float | None = None,
    ) -> ExplanationResult:
        """构造模板回退结果。"""

        trail = ExplanationAuditTrail(
            facts_hash=facts.facts_hash(),
            template_version=self.renderer.version,
            template_hash=template_hash,
            prompt_version=PROMPT_VERSION,
            provider_name=provider_name,
            model_version=model_version,
            adapter_version=adapter_version,
            latency_ms=latency_ms,
            lora_candidate_hash=self._text_hash(raw_llm_output)
            if raw_llm_output
            else None,
            explanation_mode_requested=mode,
            explanation_mode_used="template"
            if fallback_reason in {"mvp_template_default", "high_risk_template_only"}
            else mode,
            final_source="template"
            if fallback_reason in {"mvp_template_default", "shadow_mode_template_default"}
            else "fallback",
            raw_llm_output=raw_llm_output,
            raw_lora_output_saved=raw_llm_output is not None,
            raw_lora_output_saved_reason=(
                "local_trace_for_guard_audit"
                if raw_llm_output is not None
                else "no_lora_output"
            ),
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

    def _rewrite_request_mode(self, mode: ExplanationMode) -> str:
        """把兼容旧模式和产品模式转换为 provider 输入。"""

        if mode in {"experimental", "guarded_lora"}:
            return "guarded_lora"
        return "shadow_lora"

    def _is_shadow_mode(self, mode: ExplanationMode) -> bool:
        """判断是否只观测 rewrite，不用于最终输出。"""

        return mode in {"shadow", "shadow_lora"}

    def _provider_unavailable_reason(self, mode: ExplanationMode) -> str:
        """新 API 使用 provider_unavailable，旧 experimental 保持兼容。"""

        return "provider_unavailable" if mode in {"guarded_lora", "shadow_lora"} else "lora_unavailable"

    def _text_hash(self, text: str) -> str:
        """生成解释文本 hash，避免 trace 只能靠原文比对。"""

        return hashlib.sha256(text.encode("utf-8")).hexdigest()
