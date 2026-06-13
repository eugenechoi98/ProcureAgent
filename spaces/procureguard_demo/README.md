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

1. Invoice Audit
2. Model Lab
3. Architecture

当前公开 Demo：

- 不加载 LayoutLMv3
- 不加载 Qwen
- 不加载真实 LoRA
- 不需要 GPU
- 不需要 API Key
- 不需要 secrets
- Model Lab 展示真实离线 artifacts，不是网页实时推理

## Runtime Boundary

Invoice Audit 使用预生成字段和本地确定性审核链。Model Lab 仅读取轻量 JSON
artifacts。Architecture 只解释系统边界。当前没有创建生产服务，也没有启用
线上模型推理。
