"""Architecture 页签只读说明。"""

from __future__ import annotations

from typing import Any


ARCHITECTURE_MARKDOWN = """
## 系统架构

**ProcureGuard AI 是受控采购审核 Agent，不是让大模型自主决定风险的系统。**

本页解释模型、规则链和受控解释层各自负责什么，以及为什么模型不能直接决定风险。
采购审核的风险结论必须可复现、可审计。

### 系统链路

`发票图片`
-> `OCR + LayoutLMv3 字段抽取`
-> `Agent 工具`
-> `三单匹配`
-> `Policy RAG`
-> `风险规则引擎`
-> `规范化审核事实`
-> `确定性模板`
-> `受控 rewrite`
-> `Guard`
-> `模板回退`
-> `审计轨迹`
-> `审核报告`

### 治理边界

1. 模型负责抽取字段和尝试解释；模型不能直接决定风险等级。
2. 三单匹配、重复检测、Policy RAG 和风险规则引擎负责生成审核结论。
3. LoRA 不能修改风险等级，LoRA 不能修改建议动作，也不能新增异常类型。
4. Guard 用来拦截新增事实、错误动作、错误风险和缺失字段篡改。
5. 模板回退保证模型不可用、输出非法或 Guard 失败时仍返回确定性模板。
6. 审计轨迹记录输入事实、解释来源和回退原因，方便复核。
7. 第二轮 LoRA 未通过 hard gate，因此没有直接接入正式解释器。
8. 默认模板路径仍有价值，因为它离线、稳定、可审计，不依赖模型或 API Key。

### 运行边界

- 公网 Demo 中，LayoutLMv3 图片推理以离线检查点证据包形式展示；
  第二阶段审核链和 Guard / 模板回退为轻量 CPU 可运行逻辑。
- 当前 Space 不上传模型权重，不执行任意图片实时推理。
- 发票审核页以已验收证据包展示图片到审核报告的完整链路。
- 模型实验展示真实离线证据包。
- 系统架构只解释工程与治理边界。
- 当前网页不加载 LayoutLMv3、Qwen 或真实 LoRA。
- 当前已部署 CPU 版 Hugging Face Space，但不加载模型或启用 GPU。
"""


def build_architecture_tab(gr: Any) -> None:
    """构建 Architecture 页签。"""

    gr.Markdown(ARCHITECTURE_MARKDOWN, elem_id="architecture-summary")
