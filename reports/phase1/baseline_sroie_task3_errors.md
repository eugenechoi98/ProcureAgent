# Phase 1 Baseline Error Analysis

- error_count: 337
- error_count_by_field: {'address': 141, 'date': 40, 'total': 95, 'company': 61}
- error_type_distribution: {'layout_change': 202, 'regex_rule_miss': 52, 'unknown': 83}

## Representative Cases

| sample_id | field | predicted | ground_truth | error_type | notes |
| --- | --- | --- | --- | --- | --- |
| 68f28c63d47a8203ad798055 | address | m4-a-8, jalan pandah indah 4/1a, | m4-a-8, jalan pandah indah 4/1a, pandah indah, 55100 kuala lumpur. | layout_change | Heuristic line selection likely picked the wrong region. |
| 68f28c60d47a8203ad797f8c | address | gst ref no : 001694261248 | domino's pizza taman universiti 30, jln kebudayaan 7, tmn universiti 81300 skudai, johor | layout_change | Heuristic line selection likely picked the wrong region. |
| 68f28c60d47a8203ad797f8c | date |  | 28/04/18 | regex_rule_miss | Regex baseline did not produce a value. |
| 68f28c60d47a8203ad797f8c | total |  | 39.60 | regex_rule_miss | Regex baseline did not produce a value. |
| 68f28c64d47a8203ad798081 | address | no 1&3, jalan angsa delima 12, | no 1&3, jalan wangsa delima 12, wangsa link, wangsa maju, 53300 kuala lumpur | layout_change | Heuristic line selection likely picked the wrong region. |
| 68f28c64d47a8203ad798081 | total | 70.00 | 83.00 | unknown | No deterministic category matched. |
| 68f28c61d47a8203ad797fd1 | company | your order number is | golden arches restaurants sdn bhd | layout_change | Heuristic line selection likely picked the wrong region. |
| 68f28c61d47a8203ad797fd1 | address | golden arches restaurants sdn bhd | level 6, bangunan th, damansara uptown3 no.3, jalan ss21/39,47400 petaling jaya selangor | layout_change | Heuristic line selection likely picked the wrong region. |
| 68f28c61d47a8203ad797fd1 | total | 2.00 | 29.30 | unknown | No deterministic category matched. |
| 68f28c67d47a8203ad798123 | company | popular book | popular book co. (m) sdn bhd | layout_change | Heuristic line selection likely picked the wrong region. |
