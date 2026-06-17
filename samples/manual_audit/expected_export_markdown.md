# Expected Markdown Export Shape

运行时导出包含以下稳定章节；动态 `audit_id`、`trace_id` 和时间不固定：

- Boundary notice
- Audit Metadata
- Invoice Fields
- Explicit Mock Procurement Context
- Deterministic Audit Result
- Evidence and Explanation
- Source And Fallback Status
- Human Review
- Warnings

报告必须明确 `payment_authority=false`，并保留 deterministic risk/action 与 reviewer decision 的分离。
