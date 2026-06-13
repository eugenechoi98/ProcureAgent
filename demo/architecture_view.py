"""Architecture 页签只读说明。"""

from __future__ import annotations

from typing import Any


ARCHITECTURE_MARKDOWN = """
## Architecture

### System Chain

`Invoice`
-> `OCR + LayoutLMv3`
-> `Agent Tools`
-> `Three-Way Match`
-> `Policy RAG`
-> `Risk Engine`
-> `Canonical Facts`
-> `Deterministic Template`
-> `Optional Controlled Rewrite`
-> `Guard`
-> `Fallback`
-> `Audit Trail`
-> `AuditReport`

### Governance Boundary

1. 模型不能直接决定 risk，因为采购审核需要可复现的金额、匹配和政策证据。
2. LoRA 不能改变 `risk_level`，风险等级只来自确定性 Risk Engine。
3. LoRA 不能改变 `recommended_action`，建议动作只来自封板规则链。
4. LoRA 不能新增异常类型，异常类型来自三单匹配、重复检测和 Policy RAG。
5. Guard 用来拦截改写中的新增事实、错误动作、错误风险和缺失字段篡改。
6. Fallback 保证模型不可用、输出非法或 Guard 失败时仍返回确定性模板。
7. 第二轮 LoRA 未过 hard gate：format、factual consistency、action consistency、anomaly coverage 和 hallucination 均未达上线门槛。
8. 第三次训练暂停，因为继续训练前需要先收口事实边界和展示治理，不把失败 adapter 接入主链。
9. 默认模板路径仍然有价值，因为它离线、稳定、可审计、不需要模型和 API Key。
10. 后续 optional live inference 包括在线 LayoutLMv3、在线真实 LoRA、GPU Space、Phase 3I、LangChain Policy RAG 对比、Docker 和 CI。

### Runtime Boundary

- Invoice Audit 是当前可运行路径。
- Model Lab 展示真实离线 artifacts。
- Architecture 只解释系统边界。
- 当前网页不加载 LayoutLMv3、Qwen 或真实 LoRA。
- 当前已部署 CPU-only Hugging Face Space，但不加载模型或启用 GPU。
"""


def build_architecture_tab(gr: Any) -> None:
    """构建 Architecture 页签。"""

    gr.Markdown(ARCHITECTURE_MARKDOWN, elem_id="architecture-summary")
