# Phase 3E First LoRA Evaluation Review

## By Anomaly Type

| model | anomaly_type | samples | format | factual | action | anomaly coverage | hallucination rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | amount_discrepancy | 2 | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 |
| base | duplicate_invoice | 2 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| base | high_value_approval_required | 3 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| base | missing_goods_receipt | 3 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| base | missing_po_number | 2 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| base | multi_issue_combination | 3 | 0.0000 | 0.6667 | 0.0000 | 0.0000 | 0.3333 |
| base | quantity_mismatch | 2 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| base | vendor_name_mismatch | 3 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| fine_tuned | amount_discrepancy | 2 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| fine_tuned | duplicate_invoice | 2 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| fine_tuned | high_value_approval_required | 3 | 0.0000 | 1.0000 | 1.0000 | 0.6667 | 0.0000 |
| fine_tuned | missing_goods_receipt | 3 | 0.3333 | 0.3333 | 1.0000 | 1.0000 | 0.6667 |
| fine_tuned | missing_po_number | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| fine_tuned | multi_issue_combination | 3 | 0.0000 | 0.6667 | 1.0000 | 0.2222 | 0.3333 |
| fine_tuned | quantity_mismatch | 2 | 0.0000 | 0.5000 | 0.5000 | 1.0000 | 0.5000 |
| fine_tuned | vendor_name_mismatch | 3 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 |

## Hallucinations

### base
- `phase3-multi_issue_combination-023` `multi_issue_combination` unknown_identifier:PO-20260198 -> identifier_filled_by_pattern

### fine_tuned
- `phase3-quantity_mismatch-024` `quantity_mismatch` unknown_amount:8100.24 -> amount_fact_not_constrained
- `phase3-missing_goods_receipt-024` `missing_goods_receipt` unknown_identifier:GRN-20260149 -> missing_grn_filled_by_pattern
- `phase3-missing_goods_receipt-025` `missing_goods_receipt` unknown_identifier:GRN-20260150 -> missing_grn_filled_by_pattern
- `phase3-multi_issue_combination-024` `multi_issue_combination` unknown_vendor:Adventure Works Services 不匹配 -> vendor_relation_overgeneralized

## Format Failure Distribution

```json
{
  "base": {
    "missing_anomaly_type": 18,
    "missing_critical_facts": 20,
    "missing_fixed_sections": 20,
    "missing_recommended_action": 20,
    "missing_risk_level": 20
  },
  "fine_tuned": {
    "missing_anomaly_type": 6,
    "missing_critical_facts": 14,
    "missing_fixed_sections": 7,
    "missing_recommended_action": 3,
    "missing_risk_level": 1
  }
}
```

## Dataset Diagnostics

```json
{
  "train": {
    "sample_count": 160,
    "anomaly_type_counts": {
      "amount_discrepancy": 20,
      "duplicate_invoice": 20,
      "high_value_approval_required": 20,
      "missing_goods_receipt": 20,
      "missing_po_number": 20,
      "multi_issue_combination": 20,
      "quantity_mismatch": 20,
      "vendor_name_mismatch": 20
    },
    "multi_issue_count": 20,
    "section_shape_counts": {
      "('异常类型', '关键事实', '审核结论')": 160
    },
    "risk_flags": {
      "no_negative_constraint_in_answer": 160
    }
  },
  "validation": {
    "sample_count": 20,
    "anomaly_type_counts": {
      "amount_discrepancy": 3,
      "duplicate_invoice": 3,
      "high_value_approval_required": 2,
      "missing_goods_receipt": 2,
      "missing_po_number": 3,
      "multi_issue_combination": 2,
      "quantity_mismatch": 3,
      "vendor_name_mismatch": 2
    },
    "multi_issue_count": 2,
    "section_shape_counts": {
      "('异常类型', '关键事实', '审核结论')": 20
    },
    "risk_flags": {
      "no_negative_constraint_in_answer": 20
    }
  },
  "test": {
    "sample_count": 20,
    "anomaly_type_counts": {
      "amount_discrepancy": 2,
      "duplicate_invoice": 2,
      "high_value_approval_required": 3,
      "missing_goods_receipt": 3,
      "missing_po_number": 2,
      "multi_issue_combination": 3,
      "quantity_mismatch": 2,
      "vendor_name_mismatch": 3
    },
    "multi_issue_count": 3,
    "section_shape_counts": {
      "('异常类型', '关键事实', '审核结论')": 20
    },
    "risk_flags": {
      "no_negative_constraint_in_answer": 20
    }
  }
}
```

## Prompt Diagnostics

```json
{
  "only_reference_input_facts": true,
  "forbid_unknown_amounts_identifiers_vendors": true,
  "forbid_change_risk_level_or_action": true,
  "requires_fixed_sections": true,
  "requires_missing_fields_literal": false
}
```

## Generation Diagnostics

```json
{
  "generation": {
    "do_sample": false,
    "max_new_tokens": 256
  },
  "inactive_sampling_keys": [],
  "recommendation": "no inactive sampling keys found"
}
```

## Recommendation

{
  "variable": "fact_constrained_prompt_and_uniform_expected_explanation_format",
  "reason": "The first run improved action and anomaly coverage, but hallucination and format failures show the model learned the task intent before learning hard fact boundaries.",
  "expected_improvements": [
    "format_compliance",
    "factual_consistency",
    "hallucination_rate",
    "anomaly_coverage"
  ]
}

## Hard Gates

{
  "factual_consistency": 0.95,
  "hallucination_rate_max": 0.05,
  "action_consistency": 0.9,
  "anomaly_coverage": 0.9,
  "format_compliance": 0.9
}
