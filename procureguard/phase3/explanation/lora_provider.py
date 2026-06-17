"""LoRA rewrite provider 运行时接口与本地不可用占位实现。"""

from __future__ import annotations

from time import perf_counter

from procureguard.phase3.explanation.rewrite_contract import (
    RewriteRequest,
    RewriteResponse,
)


class UnavailableLoRARewriteProvider:
    """clean clone 默认 provider：不伪造 adapter，只返回不可用错误。"""

    provider_name = "unavailable_lora_provider"

    def __call__(self, request: RewriteRequest) -> RewriteResponse:
        """返回空候选，让 orchestrator fail closed 到模板。"""

        started = perf_counter()
        return RewriteResponse(
            raw_text="",
            provider_name=self.provider_name,
            model_version="unavailable",
            adapter_version="unavailable",
            latency_ms=(perf_counter() - started) * 1000,
            error=(
                "No real LoRA adapter is wired in this runtime. "
                "Template fallback remains the supported clean-clone path."
            ),
        )
