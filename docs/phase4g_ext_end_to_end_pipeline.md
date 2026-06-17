# Phase 4G-EXT：End-to-End Audit Pipeline Closure

## 结论

Phase 4G-EXT 新增统一端到端 API：

```text
POST /api/mvp/audit/execute
```

开发者可以用一个入口完成：

```text
Invoice Image / Field Candidates / Confirmed Fields
-> Field Confirmation Layer
-> Confirmed ExtractedFields
-> Phase 2 Deterministic Audit
-> AuditReport
-> Deterministic Explanation
-> JSON + Markdown + Trace
```

## 输入来源

API 支持三种来源：

1. `image`：运行本地 OCR + LayoutLMv3，得到 candidates，再进入 confirmation。
2. `field_candidates`：直接进入 confirmation。
3. `confirmed_fields`：已确认字段，直接作为审计事实输入。

除 `confirmed_fields` 外，所有来源都必须提供 `confirmation_decisions`。raw OCR text 或 raw LayoutLMv3 candidate 不能直接进入 Phase 2。

## Phase 2 Contract

Phase 2 只接受：

```text
ConfirmedAuditInput.confirmed_fields
```

端到端编排内部通过 `confirmed_audit_input_to_extracted_fields()` 取出 `ExtractedFields`。该路径禁止：

- raw model output bypass
- OCR raw text bypass
- unconfirmed candidates bypass
- confidence 影响 risk/action

## Trace

每次执行返回：

```json
{
  "ocr_used": true,
  "layoutlmv3_used": true,
  "fields_confirmed_by": "human|simulated_human|provided_confirmed_fields",
  "fields_modified": [],
  "phase2_decision_source": "deterministic_rules",
  "risk_level_origin": "rules_only",
  "recommended_action_origin": "rules_only",
  "explanation_mode_requested": "template|guarded_lora|shadow_lora",
  "explanation_mode_used": "template|guarded_lora|shadow_lora",
  "fallback_reason": "provider_unavailable|null"
}
```

## Output

返回结构包含：

- `json`：AuditReport、trace、image trace 和 export metadata。
- `markdown`：可读 AuditReport。
- `trace`：AI + human + rules 的来源链。

## LoRA / Guard Boundary

LoRA 仍只是 explanation candidate。Phase 4H 后推荐使用 `guarded_lora` 或 `shadow_lora`：

- `template`：不调用 provider。
- `guarded_lora`：Guard PASS 才使用 LoRA rewrite；FAIL 或 provider unavailable fallback deterministic template。
- `shadow_lora`：只记录候选和 Guard 结果，最终始终返回 template。

无论 Guard pass/fail，`risk_level` 和 `recommended_action` 都已经由 Phase 2 deterministic rules 生成。

## 当前边界

- API 可以真实运行 image path，但 CPU OCR/LayoutLMv3 较慢；测试使用 fake image runner 覆盖 image path contract。
- 采购上下文仍是 explicit mock PO/GRN，不是企业 ERP。
- 当前没有生产认证、多租户、持久 workspace 或付款权限。
