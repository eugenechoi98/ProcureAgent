"""Architecture 页签只读说明。"""

from __future__ import annotations

from typing import Any


ARCHITECTURE_MARKDOWN = """
## 系统架构

**本页解释为什么模型不能直接决定风险、为什么 LoRA 只能做受控解释，以及 Guard / Fallback 如何保护审核链路。**

### 系统链路

`发票`
-> `OCR + LayoutLMv3 字段抽取`
-> `Agent 工具链`
-> `三单匹配`
-> `政策 RAG`
-> `风险规则引擎`
-> `标准审核事实`
-> `确定性解释模板`
-> `可选受控改写`
-> `输出守卫（Guard）`
-> `模板回退（Fallback）`
-> `审计轨迹`
-> `审核报告`

### 治理边界

1. 模型不能直接决定风险等级，因为采购审核需要可复现的金额、匹配和政策证据。
2. LoRA 不能修改风险等级，风险等级只来自确定性风险规则引擎。
3. LoRA 不能修改建议动作，建议动作只来自封板规则链。
4. LoRA 不能新增异常类型，异常类型来自三单匹配、重复检测和 Policy RAG。
5. 输出守卫用于拦截新增事实、错误动作、错误风险和缺失字段篡改。
6. 模板回退保证模型不可用、输出非法或守卫失败时仍返回确定性解释。
7. 第二轮 LoRA 未通过 hard gate，因此没有直接接入正式解释器。
8. 第三次训练暂停，原因是当前收益不如先完成可展示工程闭环。
9. 默认模板路径仍有价值，因为它离线、稳定、可审计，不依赖模型或 API Key。
10. 后续 optional live inference 包括在线 LayoutLMv3、在线真实 LoRA 和 GPU Space。

### 运行边界

- 发票审核是当前可运行路径。
- 模型实验展示真实离线 artifacts。
- 系统架构只解释工程与治理边界。
- 当前网页不加载 LayoutLMv3、Qwen 或真实 LoRA。
- 当前已部署 CPU-only Hugging Face Space，但不加载模型或启用 GPU。
"""


def build_architecture_tab(gr: Any) -> None:
    """构建 Architecture 页签。"""

    gr.Markdown(ARCHITECTURE_MARKDOWN, elem_id="architecture-summary")
