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
- ModelScope 适配层只负责识别镜像并复制整图和 OCR annotation；crop OCR 标签不会被伪装成四字段 entity ground truth。
- Hugging Face Task 3 适配层读取 FiftyOne `samples.json` 中的 entity metadata 和 OCR detections，生成固定 seed 的 train/validation processed JSONL。
- LayoutLMv3 训练优先使用数据集 OCR annotation，PaddleOCR 单独验证端到端图片推理路径。
- GPU Notebook 在 ModelScope 与 Colab 共享同一训练主体，环境差异只放在初始化单元格。
- 训练输出按 best field macro F1 保存 checkpoint，并导出日志、loss 曲线、token F1、field F1 和错误分析。
- `gpu_notebook.py` 统一负责 Kernel 依赖验证、跨平台图片路径修复、本地模型检查和训练 guard。
- bootstrap 脚本可写修复与环境摘要，verify 脚本只读检查；Notebook 只调用统一入口，不重复环境逻辑。
- `gpu_notebook_context.py` 在当前 Notebook Kernel 内一次性恢复真实 BIO 标签、样本、processor、Torch、device 和训练配置，避免依赖子进程注入变量。
- 本地 LayoutLMv3 只接受 `model.safetensors`，processor 和模型均离线加载，不回退到 `pytorch_model.bin`。
- 字段重建统一经过 `field_reconstruction.py`；日期 span 会去掉 `DATE:`、时间和其他非日期文本。
- Phase 1 离线 hybrid 采用 LayoutLMv3 抽取 company/address/total、Regex 抽取 date，尚未接入 API。
- `compare_date_reconstruction.py` 复用同一 checkpoint token predictions，对比旧/新日期重建并输出实际 F1 恢复，不触发训练。
