# Phase 3 Dataset Summary

- synthetic_only: true
- seed: 42
- sample_count: 200

## Split Counts

| split | count |
| --- | ---: |
| test | 20 |
| train | 160 |
| validation | 20 |

## Anomaly Type Counts

| anomaly_type | count |
| --- | ---: |
| amount_discrepancy | 25 |
| duplicate_invoice | 25 |
| high_value_approval_required | 25 |
| missing_goods_receipt | 25 |
| missing_po_number | 25 |
| multi_issue_combination | 25 |
| quantity_mismatch | 25 |
| vendor_name_mismatch | 25 |

## File Hashes

- `train.jsonl`: `6e7d3396f6aba96b28d07306c9389f2803e725bca97a65ea02d7c1ffaf9bdf63`
- `validation.jsonl`: `881957710018da129323b05ce1518863e45caa7171a114bf278c0d90718db733`
- `test.jsonl`: `1e11910d46ffe6338538904a2374021a4a76331517ef0d12c055ea868b5729dd`

## Gold Answer Contract

- 固定章节：`异常类型`、`事实边界`、`关键事实`、`缺失字段`、`禁止补全`、`审核结论`。
- 缺失字段必须写 `未提供` 或 `缺失`。
- 不得补全 PO、GRN、发票号、金额、供应商或未输入异常类型。
- 多异常组合只覆盖 `input_facts.anomaly_types` 中存在的异常。
