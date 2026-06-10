# Phase 1A Baseline Error Analysis

| sample_id | field | predicted | ground_truth | error_type | notes |
| --- | --- | --- | --- | --- | --- |
| receipt_error | address | northwind industrial | 88 river road | layout_change | Heuristic line selection likely picked the wrong region. |
| receipt_error | total |  | 600.00 | regex_rule_miss | Regex baseline did not produce a value. |
