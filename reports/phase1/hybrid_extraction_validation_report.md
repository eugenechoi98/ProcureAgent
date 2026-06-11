# Hybrid Extraction Validation Report

- evaluation_type: offline
- evaluation_split: local_validation_split_seed_42
- official_test: false
- integrated_into_api: false
- strategy: company/address/total=LayoutLMv3, date=OCR+Regex baseline
- phase1_status: fallback_only

| field | regex_baseline_f1 | layoutlmv3_f1 | hybrid_f1 |
| --- | ---: | ---: | ---: |
| company | 0.5704 | 0.7068 | 0.7068 |
| address | 0.0070 | 0.7376 | 0.7376 |
| date | 0.8293 | 0.1423 | 0.8293 |
| total | 0.3481 | 0.9058 | 0.9058 |
| macro | 0.4387 | 0.6231 | 0.7949 |

Phase 1G corrected pure LayoutLMv3 macro F1=0.8067，高于本报告 Hybrid 的 0.7949。
因此 Hybrid 不再是 Phase 1 MVP 默认离线策略，仅保留为 fallback 思路。
