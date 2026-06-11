# DECISIONS.md

## 2026-06-11：LayoutLMv3 训练只允许加载 Safetensors
本地模型目录必须包含 `model.safetensors`，训练与验证显式使用 `use_safetensors=True` 和 `local_files_only=True`。不允许回退到 `pytorch_model.bin`，避免触发 `torch.load` 安全限制。

## 2026-06-11：首次 GPU 微调采用固定本地 validation split
首次 NVIDIA A10 微调结果使用 `local_validation_split_seed_42`，macro F1 为 0.6231。该结果用于 baseline 对比和工程决策，不表述为 official test。

## 2026-06-11：Phase 1 先保留 hybrid 离线策略
同一 validation split 上，LayoutLMv3 抽取 company/address/total、Regex 抽取 date 的 hybrid macro F1 为 0.7949。先将其作为可展示的离线方案，不接入 API；第二轮先用现有 checkpoint 验证日期重建修复，不调整 epoch 或学习率。

## 2026-06-11：GPU Notebook 将环境验证与 Kernel 状态恢复分离
bootstrap 子进程只负责依赖、路径、模型和 guard，不能承担 Notebook 变量注入。当前 Kernel 统一调用 runtime context 构建函数恢复标签、样本、processor、Torch、device 和训练参数，并在 Dataset 前一次性 preflight，避免逐个 NameError。

## 2026-06-11：GPU 训练环境以 Notebook Kernel 为唯一真源
ModelScope Terminal 与 Notebook Kernel 可能使用不同 Python 和 Torch。Phase 1 GPU 训练统一通过 `sys.executable` 安装和验证依赖，模型使用本地目录，processed JSONL 由 bootstrap 统一修复；只有训练 guard 通过后才允许进入训练。

## 2026-06-10：模型抽取依赖与默认后端依赖隔离
FastAPI 默认运行环境保持轻量，不强制安装 Torch、Transformers、PaddleOCR 和 PaddlePaddle。Phase 1 通过 extraction optional dependency group 安装模型依赖。LayoutLMv3 训练优先使用数据集提供的 OCR annotation，以单独评估字段抽取能力；PaddleOCR 用于端到端真实推理路径和 smoke 验证。

## 2026-06-10：Phase 1 先做独立抽取模块，不直接接入上传接口
Phase 2 后端真实规则链已经封板，Phase 1 只产出可替换 API 占位字段的模型抽取能力。这样可以先完成 OCR、LayoutLMv3、字段级 F1 和错误分析，不影响已通过的后端接口、工具签名和 Risk Engine。

## 2026-06-10：Agent 工具数量固定为 5 个
MVP 保持 5 个工具：查 PO、查收货、查重复、查政策、提交人工审核。这 5 个工具已经覆盖完整审核主链，不额外补没有明确业务价值的第 6 个工具。

## 2026-06-10：重复检测结果必须回写 ValidationResult
`check_duplicate_invoice` 的工具结果必须显式更新 `ValidationResult.duplicate_check`，否则 Risk Engine 会永远读到默认值，重复发票无法进入高风险分支。

## 2026-06-10：Policy RAG 使用 SQLite FTS5 和 mock 政策数据
Policy RAG 需要真实可检索的数据表与初始化数据，MVP 使用 `policy_documents` 加 `policy_fts`，先覆盖审批阈值、三单匹配、重复发票、数量误差、金额误差等演示场景。

## 2026-06-10：业务输出使用 AuditReport schema，不套 ContextPack
ContextPack 属于 ContextGraph Studio 的 AI Coding Agent 输出格式。ProcureGuard 是采购审核业务系统，最终结构化输出统一使用 `AuditReport` schema。

## 2026-06-10：重复发票采用确定性直接拒绝
重复发票属于高风险硬规则。检测到相同供应商与发票号重复提交后，将 `ValidationResult.duplicate_check` 写为 `False`，风险等级设为 `high`，建议动作设为 `reject`，不进入普通人工审核队列。
