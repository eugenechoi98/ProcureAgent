# Phase 4D AuditReport Export & Human Review UX

## 目标

Phase 4D 在手动审核入口上补齐本地 MVP 闭环：

```text
Manual Audit
-> Process-memory MVP Store
-> JSON / Markdown Export
-> Human Review Queue / Decision
-> Export With Review Metadata
```

本轮不修改 Phase 2 数据库 schema，不接 ERP、付款、认证、多租户、在线 LayoutLMv3 或在线 LoRA。

## 存储策略

采用应用进程内 `ManualAuditStore`：

- Manual Audit API 成功后保存原请求、AuditReport、source labels、fallback status 和 review metadata。
- store 只在当前 API 进程有效，服务重启后清空。
- 不写默认 SQLite，不修改 Phase 2 invoice/review 表。
- 该方案只用于本地 MVP，不是生产持久化、审计留存或恢复机制。

## API

```text
POST /api/mvp/manual-audit
GET  /api/mvp/manual-audit/review-queue
POST /api/mvp/manual-audit/{audit_id}/review
GET  /api/mvp/manual-audit/{audit_id}/export?format=json
GET  /api/mvp/manual-audit/{audit_id}/export?format=markdown
```

人工决定支持：

- `approve`
- `reject`
- `request_more_info`

人工决定是附加元数据，不会修改原始 `risk_level`、`recommended_action`、policy flags 或 evidence。低风险且无需人工审核的记录不能伪造 required review。

## 导出格式

### JSON

稳定机器可读结构包含：

- audit/trace ID、generated_at 和边界提示；
- manual invoice fields；
- explicit mock procurement context summary；
- deterministic risk/action、validation、evidence 和 explanation；
- source labels、fallback status 和 explanation mode；
- review status、decision、note 和 reviewed_at；
- `payment_authority=false` 与 `deterministic_result_unchanged=true`。

### Markdown

固定章节适合复制到面试说明或本地审核记录：Audit Metadata、Invoice Fields、Explicit Mock Context、Deterministic Result、Evidence、Explanation、Source/Fallback、Human Review 和 Warnings。

Markdown 顶部明确声明它不是付款凭证、合规批准或企业采购记录。

## Sample

仅运行并打印结果：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case all
```

提交本地 reviewer note 并导出 Markdown：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py `
  --case missing_grn `
  --review "Need PO owner confirmation" `
  --decision request_more_info `
  --export markdown `
  --output-dir samples\manual_audit\generated
```

导出 JSON：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py `
  --case amount_mismatch `
  --export json `
  --output-dir samples\manual_audit\generated
```

`generated/` 已被 Git 忽略。没有 `--output-dir` 时脚本不会写文件。

## 状态与边界

所有结果、队列、review response 和 export 保留：

- `invoice_field_source=manual_input`
- `procurement_context_source=explicit_mock_context`
- `risk_decision_source=deterministic_rules`
- `explanation_source=deterministic_template`
- `live_layoutlmv3_used=false`
- `live_lora_used=false`
- `payment_authority=false`
- fallback、review status、decision 和 reviewer note

人工审核只是本地 MVP 演示，不代表真实企业审批。当前没有生产级认证、权限、隐私 SLA、持久审计日志或并发工作流。
