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

ProcureGuard AI 是采购发票智能审核 Agent 的 CPU-only 作品集 Demo。

页面包含：

1. Path A 手动审核：无 ML，手动字段直接进入确定性审核
2. Path B Scenario Demo：5 个案例，每个案例都有图片、Run Audit 和 Audit Result
3. 系统说明：架构、边界和 trace/log 说明

当前公开 Demo：

- 不加载 LayoutLMv3
- 不加载 Qwen
- 不加载真实 LoRA
- 不需要 GPU
- 不需要 API Key
- 不需要 secrets
- Path B 展示流程驱动 UI，不使用纯文本案例页
- 5 个案例都有发票图片、Run Audit 按钮和结果卡片
- 每张发票图片绑定唯一 scenario_id，Run Audit 会加载该 scenario 的固定字段映射
- 所有 scenario OCR 字段均为非空值，不展示空字段或失败状态
- LoRA OFF/ON 切换放在 Audit Result 内部，不再单独作为页面
- AI 图片链路是预置场景驱动展示，不是网页实时推理

## 运行边界

发票图片会绑定固定 scenario_id；字段展示、审计输入和解释文本均来自该 scenario
的预置映射。页面不调用 OCR 模型、不调用 LayoutLMv3、不随机生成字段。LoRA 只做
解释语言增强，不影响 risk_level 或 recommended_action。当前没有启用线上模型推理，
也不把本作品集 Demo 表述为生产服务。
