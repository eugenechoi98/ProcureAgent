# Phase 4C User-facing MVP Input Flow

## 目标

Phase 4C 让用户无需修改代码即可提交手动发票字段和显式 mock PO/GRN 上下文，并通过现有 Phase 2 确定性审核链获得 AuditReport。

```text
Manual Invoice Fields
+ Explicit Mock PO / GRN Context
-> Request-scoped In-memory SQLite Adapter
-> Existing Phase 2 Tools / Matcher / Policy RAG / Risk Engine
-> Deterministic Template
-> AuditReport + Source Labels
```

本轮没有图片识别、在线 LayoutLMv3、在线 LoRA、ERP、付款执行、认证或多租户。

## API

```text
POST /api/mvp/manual-audit
```

请求契约位于 `procureguard.productization.manual_audit`：

- `invoice_fields`：发票号、供应商、ISO 日期、非负金额、三位货币代码、PO 号和至少一个行项目。
- `procurement_context`：用户显式提供的 mock PO、可选 GRN、重复发票标志和固定 `mock_default` policy profile。
- `metadata`：固定 `manual_input`、`explicit_mock_context` 和 `template`，可附 500 字以内备注。

不允许选择 shadow/experimental。正式响应始终使用 deterministic template。

## 上下文接入策略

采用请求级内存 SQLite adapter：

1. 每次请求创建新的 `:memory:` 数据库。
2. 初始化现有 schema 和 mock policy documents。
3. 只写入本次请求显式提供的 PO/GRN 和可选重复记录。
4. 调用原有 `AgentInvoiceProcessor.process_extracted_invoice()`。
5. 请求结束后关闭数据库。

该方案不长期污染默认 seed、不写应用数据库、不影响 sample audit 或 HF Demo，也不修改 Phase 2 工具签名。

## 响应边界

每个响应包含：

```json
{
  "source_labels": {
    "invoice_field_source": "manual_input",
    "procurement_context_source": "explicit_mock_context",
    "risk_decision_source": "deterministic_rules",
    "explanation_source": "deterministic_template",
    "live_layoutlmv3_used": false,
    "live_lora_used": false,
    "payment_authority": false
  },
  "fallback_status": {"used": false, "reason": null},
  "explanation_mode_used": "template"
}
```

Phase 3H 内部 metadata 的 `mvp_template_default` 表示正式模板默认路径，不被产品响应误标为模型 fallback。

## Sample

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case all
```

支持：

- `standard_pass`：low / auto_approve。
- `amount_mismatch`：medium / request_human_approval。
- `missing_grn`：medium / request_human_approval。

所有 sample 都是 synthetic/manual input 和 explicit mock context，不需要图片、模型权重、GPU、网络或本地持久数据库。

## API 调用

启动服务后：

```powershell
$body = Get-Content -Raw -Encoding UTF8 samples\manual_audit\request_standard_pass.json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/mvp/manual-audit `
  -ContentType "application/json" `
  -Body $body
```

也可在 `http://127.0.0.1:8000/docs` 中直接执行。

## 限制

- PO vendor、PO currency 和 PO status 当前会作为显式上下文保存，但现有 Phase 2 matcher 主要校验 PO 编号、总额和 GRN 数量；本轮不扩张规则范围。
- 手动审核结果不持久化，不能替代 Phase 4D 的导出与审核工作台。
- `audit_id` 和 `trace_id` 只标识本次响应；临时数据库关闭后不能通过现有查询接口再次读取。
- 当前没有产品级认证、权限、隐私策略或删除 SLA。
- 系统不能作为付款、合规或财务最终决策依据。
- live OCR / LayoutLMv3 延后到可选 Phase 4F；LoRA 不进入正式路径。
