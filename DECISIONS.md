# DECISIONS.md

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
