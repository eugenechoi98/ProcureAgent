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

逐样本云端预测尚未回传，因此不伪造模型错误案例。可验证的日期 OCR、alignment、候选、截断和重建证据见 `layoutlmv3_date_error_analysis.md`。
