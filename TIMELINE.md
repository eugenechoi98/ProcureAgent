# TIMELINE.md

- 2026-06-10：完成 Phase 0 架构审查决策落档，修正工具数量、AuditReport 输出、重复检测闭环和 Policy RAG schema。
- 2026-06-10：搭建 procureguard 共享契约层，完成 Pydantic 模型、SQLite schema、状态流、5 个工具接口、Policy RAG mock 数据和最小测试。
- 2026-06-10：完成共享契约层验收收口，补齐非法状态转换抛错、Policy RAG 检索样例和 9 项最小测试。
- 2026-06-10：完成共享契约层 Git 基线封板，初始化仓库并通过最小测试。
- 2026-06-10：完成 Phase 2 后端基础服务，打通上传、查询、mock 轨迹和人工审核闭环。
- 2026-06-10：完成 Phase 2 后端基础服务验收，准备进入 Agent 与规则开发。
- 2026-06-10：完成 Phase 2 Agent 与规则闭环，新增真实工具调用主链、Risk Engine 和 Agent 测试。
- 2026-06-10：完成 Phase 2 Agent 与规则模块验收，打通三单匹配、重复检测、Policy RAG、确定性风险判断和 Audit Trace。
- 2026-06-10：完成 Phase 2 集成收口，上传接口默认接入真实 AgentInvoiceProcessor 并保留显式 mock 模式。
- 2026-06-10：完成 Phase 2 总验收，真实链写入 AuditReport 和 Audit Trace，全量测试通过。
- 2026-06-10：搭建 Phase 1 模型抽取骨架，新增 PaddleOCR 适配、OCR Regex baseline、字段级 F1、错误分析和 LayoutLMv3 Notebook。
- 2026-06-10：完成 Phase 1A OCR Baseline 与 SROIE 最小闭环，支持字段级 F1 和错误分析。
- 2026-06-10：完成 Phase 1B LayoutLMv3 数据管线，补齐 BIO 对齐、Dataset、DataLoader 和训练 Notebook。
- 2026-06-10：完成 Phase 1C ModelScope SROIE 镜像适配和 987 样本 baseline 预测，确认镜像缺少四字段实体 ground truth。
- 2026-06-10：完成 Phase 1D Task 3 实体标签数据接入，补齐真实 baseline、有效 BIO 对齐和训练前验证。
- 2026-06-10：完成 Phase 1E GPU Notebook 训练准备，补齐运行手册、训练日志、checkpoint 和评测导出。
- 2026-06-11：完成 Phase 1E.1 GPU Notebook 可复现环境修复，统一 Kernel bootstrap、依赖验证、本地模型和 JSONL 路径处理。
- 2026-06-11：修复 GPU Notebook 子进程无法注入变量的问题，新增 runtime context hydrate、统一 preflight 和变量顺序审计。
