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

1. 发票审核
2. 模型实验
3. 系统架构

当前公开 Demo：

- 不加载 LayoutLMv3
- 不加载 Qwen
- 不加载真实 LoRA
- 不需要 GPU
- 不需要 API Key
- 不需要 secrets
- 发票审核页展示已验收的端到端离线证据包
- 模型实验页展示真实离线 artifacts，不是网页实时推理

## 运行边界

发票审核展示 SROIE 图片、离线 checkpoint 预测、Phase 2 审核结果与
Guard/fallback 证据；其中 PO/GRN 为明确标注的 mock 上下文。模型实验
仅读取轻量 JSON artifacts。当前没有启用线上模型推理，也不把本作品集
Demo 表述为生产服务。
