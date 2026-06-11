# LayoutLMv3 Date Error Analysis

- evaluation_split: local_validation_split_seed_42
- official_test: false
- sample_count: 142
- true_positive: 19
- false_positive: 106
- false_negative: 123
- precision: 0.1520
- recall: 0.1338
- f1: 0.1423

## Evidence Boundary

云端 142 条 checkpoint predictions 已固化到
`reports/phase1/checkpoint_inference/date_reconstruction_predictions.jsonl`。
同一批预测经日期清洗后，date F1 从 0.1423 提升到 0.8764，实际恢复 0.7341；
剩余 25 个 false negative 与此前记录的 25 个 alignment miss 对齐。

## Ground Truth Date Formats

- DD-MM-YYYY: 15
- DD/MM/YY_or_DD-MM-YY: 31
- DD/MM/YYYY: 74
- text_month: 18
- other: 4

## Observable Evidence Counts

- ocr_missing: 0
- alignment_miss: 25
- multiple_date_candidates: 30
- field_reconstruction_error: 122
- field_reconstruction_error_after_cleanup: 25
- truncation: 0

## Model-side Categories In Original Analysis

- model_classification_miss: original_analysis_did_not_classify
- normalization_error: resolved_by_checkpoint_reconstruction_comparison
- unknown: original_analysis_did_not_classify

## Prediction Format Distribution

- detailed predictions archived in `checkpoint_inference/date_reconstruction_predictions.jsonl`

## Representative Cases

### ocr_missing
- none

### alignment_miss
- `68f28c60d47a8203ad797f8c` gt=`28/04/18` candidates=['28/04/18'] reconstructed=`` cleaned=`` tokens=89
- `68f28c67d47a8203ad798123` gt=`07/01/18` candidates=['07/01/18'] reconstructed=`` cleaned=`` tokens=45
- `68f28c61d47a8203ad797fdb` gt=`02/02/17` candidates=['02/02/17'] reconstructed=`` cleaned=`` tokens=38
- `68f28c5fd47a8203ad797f5d` gt=`28/04/18` candidates=['28/04/18'] reconstructed=`` cleaned=`` tokens=77
- `68f28c62d47a8203ad798005` gt=`30-06-18` candidates=['30-06-18'] reconstructed=`` cleaned=`` tokens=52

### multiple_date_candidates
- `68f28c5fd47a8203ad797f68` gt=`17/08/2017` candidates=['17/08/2017', '17/08/2017'] reconstructed=`DATE: 17/08/2017` cleaned=`2017-08-17` tokens=86
- `68f28c63d47a8203ad798038` gt=`20/06/2018` candidates=['18/06/20', '20/06/2018', '20/06/2018'] reconstructed=`: 20/06/2018 18:07:10` cleaned=`2018-06-20` tokens=60
- `68f28c68d47a8203ad79815e` gt=`11/09/2017` candidates=['11/09/2017', '11/09/2017'] reconstructed=`DATE: 11/09/2017` cleaned=`2017-09-11` tokens=103
- `68f28c64d47a8203ad79809b` gt=`13/04/2018` candidates=['13/04/2018', '13/04/2018'] reconstructed=`: 13/04/2018 #1` cleaned=`2018-04-13` tokens=44
- `68f28c5dd47a8203ad797eef` gt=`05/08/2017` candidates=['05/08/2017', '05/08/2017'] reconstructed=`DATE: 05/08/2017` cleaned=`2017-08-05` tokens=72

### field_reconstruction_error
- `68f28c63d47a8203ad798055` gt=`30-04-2018` candidates=['30-04-2018'] reconstructed=`: 30-04-2018 19:50:14` cleaned=`2018-04-30` tokens=38
- `68f28c60d47a8203ad797f8c` gt=`28/04/18` candidates=['28/04/18'] reconstructed=`` cleaned=`` tokens=89
- `68f28c64d47a8203ad798081` gt=`23/03/2018` candidates=['23/03/2018'] reconstructed=`23/03/2018 3:13:19` cleaned=`2018-03-23` tokens=62
- `68f28c61d47a8203ad797fd1` gt=`25/12/2016` candidates=['25/12/2016'] reconstructed=`ORD #64 -REG #2- 25/12/2016 13:51:47` cleaned=`2016-12-25` tokens=40
- `68f28c67d47a8203ad798123` gt=`07/01/18` candidates=['07/01/18'] reconstructed=`` cleaned=`` tokens=45

### field_reconstruction_error_after_cleanup
- `68f28c60d47a8203ad797f8c` gt=`28/04/18` candidates=['28/04/18'] reconstructed=`` cleaned=`` tokens=89
- `68f28c67d47a8203ad798123` gt=`07/01/18` candidates=['07/01/18'] reconstructed=`` cleaned=`` tokens=45
- `68f28c61d47a8203ad797fdb` gt=`02/02/17` candidates=['02/02/17'] reconstructed=`` cleaned=`` tokens=38
- `68f28c5fd47a8203ad797f5d` gt=`28/04/18` candidates=['28/04/18'] reconstructed=`` cleaned=`` tokens=77
- `68f28c62d47a8203ad798005` gt=`30-06-18` candidates=['30-06-18'] reconstructed=`` cleaned=`` tokens=52

### truncation
- none
