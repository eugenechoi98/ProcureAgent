# CONTEXT.md

## 当前目标
推进开源可运行、真实用户可体验的受控采购发票审核 MVP。

## 当前进度
- Phase 4A-4D 已完成差距审计、开源 Quickstart、手动审核输入、导出和进程内人工复核。
- Phase 4E-R 已纠正路线：不以 SQLite persistence 为当前第一优先级，也不把项目停留在离线证据展示。
- 目标架构已恢复为图片 -> OCR tokens+bbox -> LayoutLMv3 字段候选 -> 人工确认 -> Phase 2 确定性审核 -> AuditReport -> guarded explanation。
- Phase 4F 已完成 asset checker、独立 extraction spike、字段候选 schema 和 fail-closed 契约。
- 本机 extraction 依赖可导入，但 Phase 1 微调 checkpoint、saved processor 和 BIO label map 缺失，因此真实 live inference 尚未跑通。
- Phase 4F.1 曾处于 `blocked_missing_checkpoint`；Phase 4F.2 已在 `D:\ProcureAgent_LocalArtifacts\Phase1\layoutlmv3_best.zip` 找回 artifact，并恢复 runtime bundle。
- Phase 4F.2 已完成一次真实 CPU live extraction：40 个 OCR token，4 个 LayoutLMv3 字段候选，未进入 Phase 2，未生成 risk/action。
- Phase 4G 已新增字段确认层和 `POST /api/fields/confirm`，LayoutLMv3 只作为 candidate generator，后续 Phase 2 只能读取 `ConfirmedAuditInput.confirmed_fields`。
- Phase 4G-EXT 已新增 `POST /api/mvp/audit/execute`，统一串联 image/candidates/confirmed_fields -> confirmation -> Phase 2 deterministic audit -> AuditReport JSON/Markdown/trace。
- Phase 4H 已实现 Guarded LoRA Rewrite Runtime：`template`、`guarded_lora`、`shadow_lora` 三种产品模式可用，旧 `shadow/experimental` 兼容；无真实 provider 时 fail closed 到 template。

## 下一步
建议进入 Phase 4J release readiness，先把当前可运行端到端 API、模型资产边界、mock context 和 provider unavailable 行为整理给开源用户；Phase 4I LangChain comparison 可后置。

## 注意事项
- 不把 HF Demo 稳定误判为产品完成。
- 手动字段 + mock PO/GRN 仍是稳定 fallback，但 live local LayoutLMv3 extraction 已成为后续 MVP 核心路径。
- `risk_level` 和 `recommended_action` 继续只由确定性规则生成。
- OCR 只提供 token+bbox，不替代 LayoutLMv3；字段候选需人工确认后进入 Phase 2。
- LoRA 只能作为 guarded controlled rewrite candidate，默认解释仍是 deterministic template。
- Phase 3E/3G 两轮 LoRA 未通过 hard gate；4H 只证明运行时门禁，不证明 LoRA 可靠。
- `/api/mvp/audit/execute` 支持 `guarded_lora`，但 clean clone 没有真实 LoRA adapter，会记录 `provider_unavailable` 并返回 template fallback。
- LangChain 只在 Phase 4I 做 optional comparison，不替代正式 Policy RAG。
- `.env.example` 只记录当前代码真实支持的路径变量，不代表已有环境隔离、认证或日志治理。
- Manual Audit MVP 不持久化结果，不能替代正式审核工作台或付款系统。
- Phase 4D store 仅存在于当前 API 进程，重启后审核与 reviewer note 会丢失。
- SQLite persistence、Docker hardening、HF live inference、认证和多租户均后置，不代表永久放弃。
- Phase 4F.2 的真实成功只证明单张公开样例本地可跑，不是 official test，也不证明企业发票泛化。
- confidence 不能影响 `risk_level` 或 `recommended_action`；rejected/missing 字段不能进入 audit input。
- `/api/mvp/audit/execute` 仍使用 explicit mock PO/GRN，不是企业 ERP；AuditReport 不是付款凭证。
- 工作区存在其他线程未提交的 Phase 3 和文档改动，后续不得覆盖。

## 最后更新时间
2026-06-17
