"""LoRA rewrite provider 运行时接口、本地真实 adapter 接入与不可用占位实现。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from time import perf_counter
from typing import Any

from procureguard.phase3.explanation.rewrite_contract import (
    RewriteRequest,
    RewriteResponse,
    build_rewrite_prompt,
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


@dataclass(frozen=True)
class LocalLoRAProviderConfig:
    """本地真实 LoRA provider 的显式配置。"""

    model_dir: Path
    adapter_dir: Path
    max_new_tokens: int = 256
    device: str = "auto"
    use_subprocess: bool = True
    subprocess_timeout_seconds: int = 360


class LocalLoRARewriteProvider:
    """加载本地 Qwen base model + LoRA adapter 生成受控解释候选。"""

    provider_name = "local_lora_adapter_provider"

    def __init__(self, config: LocalLoRAProviderConfig):
        self.config = config
        self._lock = Lock()
        self._loaded = False
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._device: Any | None = None
        _validate_lora_runtime_config(config)

    def __call__(self, request: RewriteRequest) -> RewriteResponse:
        """执行本地 LoRA rewrite，输出仍必须经过 Guard。"""

        if self.config.use_subprocess and os.getenv("PROCUREGUARD_LORA_WORKER") != "1":
            return self._call_subprocess(request)
        return self._call_in_process(request)

    def _call_in_process(self, request: RewriteRequest) -> RewriteResponse:
        """在当前 Python 进程内执行真实 LoRA rewrite。"""

        started = perf_counter()
        try:
            tokenizer, model = self._load()
            prompt = _prompt_for_qwen(tokenizer, request)
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            import torch

            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            new_tokens = output_ids[0, inputs["input_ids"].shape[-1] :]
            text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            return RewriteResponse(
                raw_text=text,
                provider_name=self.provider_name,
                model_version=str(self.config.model_dir),
                adapter_version=str(self.config.adapter_dir),
                latency_ms=(perf_counter() - started) * 1000,
            )
        except Exception as exc:  # noqa: BLE001
            return RewriteResponse(
                raw_text="",
                provider_name=self.provider_name,
                model_version=str(self.config.model_dir),
                adapter_version=str(self.config.adapter_dir),
                latency_ms=(perf_counter() - started) * 1000,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def _call_subprocess(self, request: RewriteRequest) -> RewriteResponse:
        """用子进程隔离 Qwen/LoRA 推理，避免污染 API 主进程。"""

        started = perf_counter()
        payload = {
            "config": {
                "model_dir": str(self.config.model_dir),
                "adapter_dir": str(self.config.adapter_dir),
                "max_new_tokens": self.config.max_new_tokens,
                "device": self.config.device,
            },
            "request": request.model_dump(mode="json"),
        }
        env = os.environ.copy()
        env["PROCUREGUARD_LORA_WORKER"] = "1"
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "procureguard.phase3.explanation.local_lora_worker",
                ],
                input=json_dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=self.config.subprocess_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return RewriteResponse(
                raw_text="",
                provider_name=self.provider_name,
                model_version=str(self.config.model_dir),
                adapter_version=str(self.config.adapter_dir),
                latency_ms=(perf_counter() - started) * 1000,
                error="local_lora_subprocess_timeout",
            )
        if completed.returncode != 0:
            stderr = completed.stderr or ""
            return RewriteResponse(
                raw_text="",
                provider_name=self.provider_name,
                model_version=str(self.config.model_dir),
                adapter_version=str(self.config.adapter_dir),
                latency_ms=(perf_counter() - started) * 1000,
                error=f"local_lora_subprocess_failed:{stderr[-1000:]}",
            )
        try:
            return RewriteResponse.model_validate_json(completed.stdout)
        except Exception as exc:  # noqa: BLE001
            return RewriteResponse(
                raw_text="",
                provider_name=self.provider_name,
                model_version=str(self.config.model_dir),
                adapter_version=str(self.config.adapter_dir),
                latency_ms=(perf_counter() - started) * 1000,
                error=f"local_lora_subprocess_parse_error:{exc}",
            )

    def _load(self) -> tuple[Any, Any]:
        """懒加载模型，避免默认 API 启动就占内存。"""

        with self._lock:
            if self._loaded and self._tokenizer is not None and self._model is not None:
                return self._tokenizer, self._model
            try:
                import torch
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "Local LoRA runtime requires torch, transformers and peft. "
                    "Install the Phase 3 LoRA environment before enabling PROCUREGUARD_LORA_ENABLED."
                ) from exc

            device = _select_device(torch, self.config.device)
            tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_dir,
                local_files_only=True,
                trust_remote_code=True,
            )
            base = AutoModelForCausalLM.from_pretrained(
                self.config.model_dir,
                local_files_only=True,
                trust_remote_code=True,
                torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
            )
            model = PeftModel.from_pretrained(
                base,
                self.config.adapter_dir,
                local_files_only=True,
            ).to(device)
            model.eval()
            self._tokenizer = tokenizer
            self._model = model
            self._device = device
            self._loaded = True
            return tokenizer, model


def provider_from_environment() -> LocalLoRARewriteProvider | None:
    """按环境变量显式启用本地真实 LoRA provider。"""

    if os.getenv("PROCUREGUARD_LORA_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
        return None
    raw_model_dir = os.getenv("PHASE3_MODEL_DIR", "")
    if not raw_model_dir.strip():
        raise RuntimeError(
            "PROCUREGUARD_LORA_ENABLED is set, but PHASE3_MODEL_DIR is not configured."
        )
    model_dir = Path(raw_model_dir).expanduser()
    adapter_dir = Path(
        os.getenv(
            "PROCUREGUARD_LORA_ADAPTER_DIR",
            "artifacts/phase3/adapters/qwen2.5-0.5b-anomaly-explainer",
        )
    ).expanduser()
    max_new_tokens = int(os.getenv("PROCUREGUARD_LORA_MAX_NEW_TOKENS", "256"))
    device = os.getenv("PROCUREGUARD_LORA_DEVICE", "auto")
    use_subprocess = os.getenv("PROCUREGUARD_LORA_SUBPROCESS", "1").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    timeout = int(os.getenv("PROCUREGUARD_LORA_TIMEOUT_SECONDS", "360"))
    return LocalLoRARewriteProvider(
        LocalLoRAProviderConfig(
            model_dir=model_dir,
            adapter_dir=adapter_dir,
            max_new_tokens=max_new_tokens,
            device=device,
            use_subprocess=use_subprocess,
            subprocess_timeout_seconds=timeout,
        )
    )


def _validate_lora_runtime_config(config: LocalLoRAProviderConfig) -> None:
    """启动前验证必要文件，缺失时拒绝伪装为真实 LoRA。"""

    missing: list[str] = []
    for name in ("config.json", "tokenizer_config.json"):
        if not (config.model_dir / name).is_file():
            missing.append(str(config.model_dir / name))
    tokenizer_ready = any(
        (config.model_dir / name).is_file()
        for name in ("tokenizer.json", "tokenizer.model", "vocab.json")
    )
    if not tokenizer_ready:
        missing.append(f"{config.model_dir}/tokenizer.json|tokenizer.model|vocab.json")
    weight_ready = bool(list(config.model_dir.glob("*.safetensors"))) or (
        config.model_dir / "model.safetensors.index.json"
    ).is_file()
    if not weight_ready:
        missing.append(f"{config.model_dir}/*.safetensors")
    if not (config.adapter_dir / "adapter_config.json").is_file():
        missing.append(str(config.adapter_dir / "adapter_config.json"))
    adapter_weights = list(config.adapter_dir.glob("adapter_model.*"))
    if not adapter_weights:
        missing.append(str(config.adapter_dir / "adapter_model.safetensors"))
    if missing:
        raise RuntimeError(
            "Local LoRA provider is enabled but required runtime files are missing: "
            + "; ".join(missing)
        )


def _select_device(torch: Any, requested: str) -> Any:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(requested)


def _prompt_for_qwen(tokenizer: Any, request: RewriteRequest) -> str:
    prompt = build_rewrite_prompt(request)
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            [
                {
                    "role": "system",
                    "content": "你是采购审核解释润色器，只能润色，不得改变事实或结论。",
                },
                {"role": "user", "content": prompt},
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
    return prompt


def json_dumps(payload: dict[str, Any]) -> str:
    """统一子进程序列化，避免 ASCII 转义影响中文 prompt。"""

    import json

    return json.dumps(payload, ensure_ascii=False)
