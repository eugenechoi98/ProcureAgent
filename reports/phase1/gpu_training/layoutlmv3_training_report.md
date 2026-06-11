# First GPU Fine-tuning Run

- gpu: NVIDIA A10
- result_source: user_confirmed_modelscope_gpu_run
- official_test: false

- data_source: Voxel51/scanned_receipts
- evaluation_split: local_validation_split_seed_42
- model_name: microsoft/layoutlmv3-base
- seed: 42
- batch_size: 2
- gradient_accumulation_steps: 4
- epochs: 5
- learning_rate: 1e-05
- best_epoch: 5
- baseline_macro_f1: 0.4387
- fine_tuned_macro_f1: 0.6231
- improvement: 0.1844

| epoch | train_loss | validation_loss | token_f1 | field_macro_f1 | learning_rate | elapsed_time |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.766641 | 0.186869 | 0.6129 | 0.2728 | 0.00000889 | 127.64 |
| 2 | 0.131864 | 0.082324 | 0.8208 | 0.5673 | 0.00000667 | 117.57 |
| 3 | 0.078481 | 0.068084 | 0.8461 | 0.5987 | 0.00000444 | 117.69 |
| 4 | 0.061553 | 0.061363 | 0.8539 | 0.6071 | 0.00000222 | 118.33 |
| 5 | 0.052902 | 0.059225 | 0.8647 | 0.6231 | 0.00000000 | 118.66 |

## Field Metrics

| field | precision | recall | f1 |
| --- | ---: | ---: | ---: |
| company | 0.8224 | 0.6197 | 0.7068 |
| address | 0.7429 | 0.7324 | 0.7376 |
| date | 0.1520 | 0.1338 | 0.1423 |
| total | 0.9328 | 0.8803 | 0.9058 |
