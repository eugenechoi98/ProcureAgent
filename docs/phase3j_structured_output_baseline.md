# Phase 3J Structured Output First Baseline

## 目标

Phase 3J 验证一个离线、可审计的结构化解释流程：

```text
Canonical Audit Facts
-> StructuredExplanation JSON
-> schema validator
-> deterministic structured renderer
-> evaluator debug report
```

本轮不训练、不下载或加载模型、不使用 GPU、不访问网络、不接 API，也不修改 Phase 1、Phase 2、Demo 或 Docker。正式默认解释仍是 Phase 3H deterministic template。Structured Output First 只是离线实验，LoRA 仍是 shadow / experimental / research。

## 独立契约

`StructuredExplanation` 位于 `procureguard.phase3.explanation`，不修改共享业务 schema：

```json
{
  "anomaly_types": ["missing_po_number"],
  "missing_fields": ["po_number"],
  "cited_evidence_ids": ["anomaly.missing_po_number", "missing.po_number"],
  "risk_level_copy": "medium",
  "recommended_action_copy": "request_human_approval",
  "explanation_bullets": [
    {
      "text": "检测到缺少采购订单号。",
      "evidence_ids": ["anomaly.missing_po_number"]
    }
  ]
}
```

关键边界：

- `risk_level_copy` 和 `recommended_action_copy` 必须与 Canonical Audit Facts 完全一致。
- `anomaly_types` 和 `missing_fields` 必须与上游集合完全一致。本 baseline 选择比“允许子集”更保守的 exact match，防止多异常漏项。
- evidence ID 由确定性程序从 Canonical Audit Facts 生成。
- 每条 bullet 必须至少绑定一个 evidence ID；顶层 `cited_evidence_ids` 必须等于 bullet 引用并集。
- 未知 PO、GRN、发票号、金额、供应商、审批角色和明显 evidence/claim 不匹配都会拒绝。

## Fail-Closed 流程

`StructuredExplanationService` 只有两种结果：

- `accepted`：schema 和事实校验全部通过，交给 structured renderer。
- `rejected`：任一检查失败，返回现有 Phase 3H deterministic template，并标记 `fallback_used=true`。

Structured renderer 只接受 `ValidatedStructuredExplanation`，并再次核对 `facts_hash`，避免把对旧事实验证过的输出用于新事实。

## Challenge Set

fixture：`tests/fixtures/phase3j_structured_challenge_set.json`

- 共 21 条 synthetic test fixtures。
- 不是企业数据，不是训练数据，不使用第二轮缺失的逐样本 artifacts。
- 5 条 rule-only 正常案例，16 条单一风险变异案例。
- 覆盖未知 PO、未知 GRN、未知金额、未知供应商、无依据审批人、多异常漏项、动作冲突、风险冲突、同义但不完整表达、非法 evidence ID、citation 并集不一致、evidence 与 bullet 不匹配、异常新增和缺失字段篡改。

## Evaluator

输出字段：

- `json_validity`
- `schema_validity`
- `risk_level_exact_match`
- `recommended_action_exact_match`
- anomaly、missing field、evidence ID 的 precision / recall
- `unsupported_claim_rate`
- `reject_reason_distribution`
- `per_case_debug_rows`

这里的字段 precision / recall 会被故意构造的非法候选拉低。baseline 是否通过不要求危险候选本身字段正确，而要求：

1. 每条 case 的 accepted/rejected 状态符合预期。
2. 指定拒绝原因被命中。
3. rejected case 全部使用模板 fallback。
4. accepted 输出的 `unsupported_claim_rate` 为 0。

## 运行

```powershell
.\.venv\Scripts\python.exe scripts\phase3\run_structured_output_baseline.py
.\.venv\Scripts\python.exe -m pytest tests\test_phase3j_structured_output.py -q
```

## 已知限制

- 本轮只验证 rule-only baseline，没有运行真实 base model JSON inference。
- evidence/claim matching 使用保守关键词规则，不能证明任意自然语言都被证据语义蕴含。
- Schema-first 能缩小输出空间，但不能替代 Phase 3H Guard / Fallback。
- 后续若加入模型输出，仍必须经过同一 validator，且不能改变风险、动作或异常类型。
