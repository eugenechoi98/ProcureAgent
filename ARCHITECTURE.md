# ARCHITECTURE.md

## 模块职责

- `procureguard.models`：冻结的共享 Pydantic 契约。
- `procureguard.api`：FastAPI 上传、查询和人工审核接口。
- `procureguard.services`：后端真实规则链、三单匹配、Policy RAG 和 Risk Engine。
- `procureguard.tools`：Agent 可调用的 5 个固定工具。
- `procureguard.extraction`：Phase 1 模型抽取模块，负责 OCR token 契约、PaddleOCR 可选适配、SROIE reader、OCR baseline、字段级 F1、错误分析和后续 LayoutLMv3 训练输入。

## 调用关系

当前主链仍由 API 层提供占位 ExtractedFields，再交给 AgentInvoiceProcessor 审核。Phase 1 暂时不接入 API，只产出独立抽取能力。后续替换时，应让上传接口调用抽取模块生成 ExtractedFields，然后复用现有 AgentInvoiceProcessor。

## Phase 1 设计

- PaddleOCR 只在实际 OCR 时延迟加载，避免普通后端运行依赖重型包。
- OCR + Regex baseline 输出独立 Phase 1 结果结构，不修改共享 ExtractedFields。
- SROIE 字段只可选映射到现有字段：company -> vendor_name，date -> invoice_date，total -> total_amount。
- 字段级 F1 和错误分析使用 normalized exact match，可在没有 GPU 和模型依赖时快速验证。
- BIO alignment 把 SROIE 字段对齐到 OCR token，标签只包含 company、address、date、total。
- LayoutLMv3 Dataset 读取 processed JSONL、图片、bbox 和 BIO labels，并使用 `apply_ocr=False` 的 processor。
- Notebook 保留手写 PyTorch 训练循环，用于后续真实 fine-tuning 和 checkpoint。
