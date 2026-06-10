# ModelScope SROIE Mirror Audit

- evaluation_status: `not_scored_missing_entity_ground_truth`
- evaluation_split: `not_available`
- train full-image samples: 626
- test full-image samples: 361
- full-image OCR annotations: 987
- entity annotations with `company/address/date/total`: 0
- train crop OCR label rows: 32902
- test crop OCR label rows: 18932
- duplicate full-image sample ids: 0
- missing image/OCR annotation pairs: 0
- `instances_test.json` image entries: 360
- test images not indexed by `instances_test.json`: `X51006619570`

`train_label.jsonl` and `test_label.jsonl` contain only `filename` and `text`. They are crop-level OCR recognition labels, not SROIE entity ground truth.

The OCR + Regex baseline ran on all 626 train samples and 361 test samples. It produced predictions, but Precision / Recall / F1 and correctness-based error analysis were intentionally not calculated because entity ground truth is absent.

## Prediction Coverage

| split | samples | company | address | date | total |
| --- | ---: | ---: | ---: | ---: | ---: |
| training | 626 | 626 | 626 | 465 | 560 |
| test | 361 | 361 | 361 | 280 | 323 |

These counts show whether the rules returned a value. They are not accuracy metrics.
