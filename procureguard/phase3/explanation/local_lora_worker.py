"""本地 LoRA 子进程 worker：隔离 Qwen/adapter 推理。"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from procureguard.phase3.explanation.lora_provider import (
    LocalLoRAProviderConfig,
    LocalLoRARewriteProvider,
)
from procureguard.phase3.explanation.rewrite_contract import RewriteRequest


def _sanitize(value):
    """替换跨进程序列化中的非法 surrogate，避免 Pydantic 拒绝解析。"""

    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    return value


def main() -> None:
    """从 stdin 读取配置和 RewriteRequest，向 stdout 写 RewriteResponse JSON。"""

    payload = json.loads(sys.stdin.read())
    raw_config = payload["config"]
    provider = LocalLoRARewriteProvider(
        LocalLoRAProviderConfig(
            model_dir=Path(raw_config["model_dir"]),
            adapter_dir=Path(raw_config["adapter_dir"]),
            max_new_tokens=int(raw_config["max_new_tokens"]),
            device=str(raw_config["device"]),
            use_subprocess=False,
        )
    )
    response = provider(RewriteRequest.model_validate(_sanitize(payload["request"])))
    sys.stdout.write(response.model_dump_json())


if __name__ == "__main__":
    main()
