# Phase 3F Dataset Diff

- base_ref: `HEAD`
- changed_expected_explanation_total: `200`
- unchanged_input_facts_for_changed_answers: `200`

| file | previous count | current count | changed answers | current sha256 |
| --- | ---: | ---: | ---: | --- |
| `data/phase3/generated/train.jsonl` | 160 | 160 | 160 | `6e7d3396f6aba96b28d07306c9389f2803e725bca97a65ea02d7c1ffaf9bdf63` |
| `data/phase3/generated/validation.jsonl` | 20 | 20 | 20 | `881957710018da129323b05ce1518863e45caa7171a114bf278c0d90718db733` |
| `data/phase3/generated/test.jsonl` | 20 | 20 | 20 | `1e11910d46ffe6338538904a2374021a4a76331517ef0d12c055ea868b5729dd` |

## First Changed Sample Per File

### data/phase3/generated/train.jsonl

```json
{
  "sample_id": "phase3-quantity_mismatch-001",
  "split": "train",
  "anomaly_type": "quantity_mismatch",
  "included_anomaly_types": [
    "quantity_mismatch"
  ],
  "expected_explanation_sha256": "5c14b44eabda950d33ddbd3a523c44d2d30329c021c30c3b825f3d0cdd401487",
  "expected_explanation_lines": 6
}
```

### data/phase3/generated/validation.jsonl

```json
{
  "sample_id": "phase3-quantity_mismatch-021",
  "split": "validation",
  "anomaly_type": "quantity_mismatch",
  "included_anomaly_types": [
    "quantity_mismatch"
  ],
  "expected_explanation_sha256": "a93f8cc7f0e4b2f3e6f664d0f016e0ac075bfb271ba596f0de92e1487a66f5f4",
  "expected_explanation_lines": 6
}
```

### data/phase3/generated/test.jsonl

```json
{
  "sample_id": "phase3-quantity_mismatch-024",
  "split": "test",
  "anomaly_type": "quantity_mismatch",
  "included_anomaly_types": [
    "quantity_mismatch"
  ],
  "expected_explanation_sha256": "118dea3351acb5624efaaaccb4ca1b2b7bcb28003449466db3dc225816a99638",
  "expected_explanation_lines": 6
}
```
