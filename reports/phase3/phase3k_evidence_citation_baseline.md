# Phase 3K Evidence Citation Baseline

## 结论

- baseline：PASS。
- 本轮没有训练、没有加载模型、没有网络、没有 GPU、没有 live inference。
- 本轮没有接 API，也没有修改 Phase 1、Phase 2、Demo 或 Docker。
- deterministic template 仍是正式默认；citation-grounded structured explanation 只是离线实验。
- LoRA 仍是 shadow / experimental / research。

## 核心指标

- citation accept/reject accuracy：1.0000
- fallback accuracy：1.0000

### Accepted-only

| metric | value |
| --- | ---: |
| evidence_id_precision | 1.0000 |
| evidence_id_recall | 1.0000 |
| claim_type_precision | 1.0000 |
| claim_type_recall | 1.0000 |
| unsupported_claim_rate | 0.0000 |
| invalid_evidence_id_rate | 0.0000 |
| mismatched_evidence_claim_rate | 0.0000 |
| missing_citation_rate | 0.0000 |

### All-candidate

| metric | value |
| --- | ---: |
| evidence_id_precision | 0.9826 |
| evidence_id_recall | 0.8692 |
| claim_type_precision | 0.9915 |
| claim_type_recall | 0.9360 |
| unsupported_claim_rate | 0.0500 |
| invalid_evidence_id_rate | 0.1000 |
| mismatched_evidence_claim_rate | 0.6000 |
| missing_citation_rate | 0.0500 |

所有候选指标包含故意构造的非法引用，因此用于观察挑战难度；是否通过以状态判断、拒绝原因、fallback 和 accepted-only 安全指标为准。

## Challenge Set

共 20 条 synthetic test fixtures，不是真实企业数据，也不是训练数据。覆盖 PO 金额、GRN 缺失、重复检查、政策阈值、风险/动作正确引用，以及未知 ID、无关证据、金额/供应商错配、无依据审批人、风险/动作冲突、多异常漏引、无 citation、claim type 错配和缺失字段补全。

## Reject Reasons

```json
{
  "anomaly_citation_missing": 1,
  "cited_evidence_ids_mismatch": 1,
  "invalid_evidence_ids": 2,
  "mismatched_evidence_claim": 12,
  "recommended_action_copy_mismatch": 1,
  "risk_level_copy_mismatch": 1,
  "schema_invalid:ValidationError": 1,
  "unsupported_claims": 1
}
```

## 边界

Evidence citation 提高了可追溯性，但不等于通用语义蕴含。当前 Claim-Evidence Validator 是保守规则，只覆盖声明类型、关键实体和稳定 evidence ID；它不能证明任意自然语言都被证据完整支持，也不能替代 Phase 3H Guard / Fallback。

未运行真实模型 JSON 输出，没有使用或补造第二轮逐样本 artifacts。
