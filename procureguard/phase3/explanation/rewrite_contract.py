"""Controlled LLM Rewrite 的输入输出契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from procureguard.phase3.explanation.facts import CanonicalAuditFacts

PROMPT_VERSION = "phase3h-controlled-rewrite-v1"


class RewriteRequest(BaseModel):
    """模型只能看到事实、模板和受控改写指令。"""

    model_config = ConfigDict(extra="forbid")

    facts: CanonicalAuditFacts
    template_output: str = Field(min_length=1)
    prompt_version: str = PROMPT_VERSION
    mode: Literal["shadow", "experimental"] = "shadow"


class RewriteResponse(BaseModel):
    """受控改写输出，raw_text 会进入 guard 和 audit trail。"""

    model_config = ConfigDict(extra="forbid")

    raw_text: str
    model_version: str = "unavailable"
    adapter_version: str = "unavailable"


def build_rewrite_prompt(request: RewriteRequest) -> str:
    """生成固定提示词，强调只能润色模板语言。"""

    facts_json = request.facts.model_dump_json(exclude_none=False)
    return (
        "你是采购审核解释润色器，只能改写语言，不能改变事实。\n"
        "硬性规则：不得新增、删除、推断或改写 Canonical Audit Facts；"
        "不得改变 risk_level、recommended_action 或 anomaly_types；"
        "必须保留模板中的固定章节标题。\n"
        f"prompt_version={request.prompt_version}\n"
        f"mode={request.mode}\n"
        f"Canonical Audit Facts={facts_json}\n"
        f"Template Output=\n{request.template_output}"
    )
