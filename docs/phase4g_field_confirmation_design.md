# Phase 4G：Field Confirmation + Deterministic Audit Integration

## 结论

Phase 4G 新增字段确认层，把 LayoutLMv3 输出隔离为候选，不允许 raw model output 直接进入 Phase 2。后续审计只能使用人工确认或修正后的 `confirmed_fields`。

```text
OCR tokens + bbox
-> LayoutLMv3 field candidates
-> Field Confirmation Layer
-> Confirmed ExtractedFields
-> Phase 2 deterministic audit
-> AuditReport
```

## 新增组件

- `procureguard.productization.field_confirmation`
- `POST /api/fields/confirm`

该 API 只做字段确认，不调用 Phase 2，不生成 AuditReport，不生成 `risk_level` 或 `recommended_action`。

## Governance Rules

字段状态：

| status | 含义 |
|---|---|
| `auto_accepted` | 非关键字段、高置信且不要求人工确认时才可自动接受 |
| `needs_review` | 中等置信或非关键字段仍需检查 |
| `must_confirm` | critical fields、低置信、缺候选或必须人工确认字段 |
| `rejected` | 用户明确拒绝 |

critical fields：

- `invoice_number`
- `total_amount`
- `vendor_name`
- `invoice_date`

critical fields 永远不能因为 LayoutLMv3 高置信而直接 auto pass。当前 live candidate 默认 `requires_human_confirmation=true`，因此所有字段都需要确认。

## Audit Input Contract

Phase 2 后续只能接收：

```text
ConfirmedAuditInput.confirmed_fields: ExtractedFields
```

禁止：

- 读取 raw LayoutLMv3 candidate。
- 以 confidence 影响风险等级。
- 让 rejected field 进入 audit input。
- 用模型 fallback 字段绕过人工确认。

允许：

- 模型提供候选。
- human override / correction。
- deterministic rules 生成最终风险和建议动作。

## 当前边界

- 本轮完成确认层和最小 API。
- 本轮不新增 UI。
- 本轮不把确认结果自动提交 Phase 2。
- Phase 2 integration 的代码入口已通过 `confirmed_audit_input_to_extracted_fields()` 限定输入来源。
- LoRA 不参与字段确认，只能在后续作为可选解释 rewrite。

## 下一步

Phase 4H 或 Phase 4G.1 可继续做：

1. 将确认后的 `ConfirmedAuditInput` 与 explicit mock PO/GRN context 组合。
2. 调用现有 Phase 2 deterministic audit。
3. 生成 AuditReport。
4. 保留 confirmation trace 到 AuditReport/export。
