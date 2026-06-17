# Phase 3J Structured Output First Baseline

## 结论

- baseline 结果：PASS。
- 本轮没有训练模型、没有加载模型、没有 GPU、没有网络推理。
- 本轮没有接 API，也没有修改 Phase 1、Phase 2、Demo 或 Docker。
- deterministic template 仍是正式默认解释路径。
- Structured Output First 只是离线实验；LoRA 仍是 shadow / experimental / research。

## 指标摘要

| metric | value |
| --- | ---: |
| json_validity | 1.0000 |
| schema_validity | 0.9524 |
| risk_level_exact_match | 0.9500 |
| recommended_action_exact_match | 0.9500 |
| anomaly_type_precision | 0.9545 |
| anomaly_type_recall | 0.9130 |
| missing_field_precision | 0.8889 |
| missing_field_recall | 0.8889 |
| evidence_id_precision | 0.9677 |
| evidence_id_recall | 0.9375 |
| unsupported_claim_rate | 0.0000 |
| expected_status_accuracy | 1.0000 |
| fallback_accuracy | 1.0000 |

字段 precision / recall 统计包含 challenge set 中故意篡改的候选，因此低于 1 不代表 validator 放行错误。baseline 通过标准是预期状态与拒绝原因命中、fallback 正确，以及 accepted 输出的 unsupported claim 为 0。

## Challenge Set

共 21 条 synthetic test fixtures，不是真实企业数据，也不是训练数据。
覆盖未知 PO、未知 GRN、未知金额、无依据审批人、未知供应商、多异常漏项、冲突动作、冲突风险、同义但不完整表达、非法 evidence id、证据与 bullet 不匹配、异常类型新增和缺失字段篡改。

## Reject Reason Distribution

```json
{
  "anomaly_types_extra": 1,
  "anomaly_types_missing": 2,
  "cited_evidence_ids_mismatch": 1,
  "invalid_evidence_ids": 1,
  "missing_fields_extra": 1,
  "missing_fields_omitted": 1,
  "recommended_action_copy_mismatch": 1,
  "risk_level_copy_mismatch": 1,
  "schema_invalid:ValidationError": 1,
  "unsupported_claims": 7
}
```

## 架构判断

rule-only baseline 证明 schema、validator、renderer、evaluator 和 fallback 可以形成离线闭环。它不证明任何 LLM 已达到上线标准，也不改变 Phase 3H 的 Template / Guard / Fallback 架构。后续若实验模型 JSON 输出，仍必须复用同一 validator，并在任何失败时回退模板。

## 未完成项

- 未运行真实 base model JSON inference；按本轮边界仅完成 rule-only baseline。
- 当前 evidence claim matching 是保守关键词校验，不是通用语义蕴含证明。
- 没有使用或补造第二轮逐样本 artifacts。
