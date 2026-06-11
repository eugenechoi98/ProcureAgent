# First GPU Run Validation Error Summary

- evaluation_split: local_validation_split_seed_42
- official_test: false
- cloud_prediction_details_available: false

| field | false_positive | false_negative |
| --- | ---: | ---: |
| company | 19 | 54 |
| address | 36 | 38 |
| date | 106 | 123 |
| total | 9 | 17 |

142 条逐样本云端预测已固化到
`checkpoint_inference/date_reconstruction_predictions.jsonl`。日期 OCR、alignment、
候选、截断和重建分析见 `layoutlmv3_date_error_analysis.md`。
