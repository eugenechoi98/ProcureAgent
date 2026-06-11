# Hybrid Extraction Validation Report

- evaluation_split: local_validation_split_seed_42
- official_test: false
- strategy: company/address/total=LayoutLMv3, date=OCR+Regex baseline

| field | regex_baseline_f1 | layoutlmv3_f1 | hybrid_f1 |
| --- | ---: | ---: | ---: |
| company | 0.5704 | 0.7068 | 0.7068 |
| address | 0.0070 | 0.7376 | 0.7376 |
| date | 0.8293 | 0.1423 | 0.8293 |
| total | 0.3481 | 0.9058 | 0.9058 |
| macro | 0.4387 | 0.6231 | 0.7949 |
