# Date Reconstruction Checkpoint Inference

- evaluation_type: offline_checkpoint_inference
- evaluation_split: local_validation_split_seed_42
- official_test: false
- integrated_into_api: false
- sample_count: 142

| reconstruction | precision | recall | f1 |
| --- | ---: | ---: | ---: |
| legacy | 0.1520 | 0.1338 | 0.1423 |
| cleaned | 0.9360 | 0.8239 | 0.8764 |

- date_f1_recovery: 0.7341
- corrected_layoutlmv3_macro_f1: 0.8067
- hybrid_macro_f1: 0.7949
- recommendation: pure_layoutlmv3_date_path
