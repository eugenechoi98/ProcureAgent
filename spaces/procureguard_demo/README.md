---
title: ProcureGuard AI
emoji: 🧾
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
---

# ProcureGuard AI

ProcureGuard AI 是一个受控采购发票审核 Agent 的公开说明与交互 Demo。

页面结构：

1. 产品总览：说明系统是什么、LayoutLMv3 做了什么、规则审核链路、LoRA/Guard/Fallback 和运行边界。
2. Scenario Demo：5 个可点击案例，每个案例都有发票图片、Run Audit、字段展示、规则结果和 LoRA OFF/ON 解释切换。
3. 完整流程视频：展示本地真实运行的上传图片 -> OCR/LayoutLMv3 -> PO/GRN lookup -> deterministic audit -> guarded LoRA explanation。
4. GitHub / 运行边界：提供 GitHub、Quickstart、架构说明和 Path A 手动审核辅助入口。

## Public Space Boundary

- 公网 Space 使用 scenario-driven deterministic demo。
- 公网 Space 不在线加载 LayoutLMv3、Qwen base model 或真实 LoRA adapter。
- 公网 Space 不需要 GPU、API Key、secrets 或企业 ERP。
- 每张 demo 发票绑定唯一 scenario_id，Run Audit 后才展示字段、规则和结果。
- `risk_level` 和 `recommended_action` 始终来自确定性规则。
- LoRA OFF/ON 只切换解释文本，不影响审核结论。
- 视频页展示的是本地真实模型链路，不代表公网 Space 实时推理。

## Links

- GitHub: https://github.com/eugenechoi98/ProcureAgent
- Space: https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
