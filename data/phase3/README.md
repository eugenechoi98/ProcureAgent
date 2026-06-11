# Phase 3 Synthetic Anomaly Explanation Dataset

本目录保存 Phase 3 LoRA 异常说明的可提交 synthetic 数据，不包含真实企业发票、供应商或政策数据。

## 数据来源与用途

- 数据由 `scripts/phase3/generate_anomaly_explanations.py` 使用固定 seed `42` 生成。
- 供应商名称、单号、金额、数量、币种、异常和证据均为程序构造。
- 数据只用于训练和评测 Qwen2.5-0.5B-Instruct 的异常说明能力。
- 模型只解释 Phase 2 已确定的事实，不计算金额、不决定风险等级、不改变建议动作。

## 数据契约

- 确定性输入：`input_facts`、`risk_level`、`recommended_action`、`anomaly_type`。
- 模型目标输出：`expected_explanation`。
- 数据管理字段：`sample_id`、`split`、`metadata`。

`input_facts` 中的单号、金额、数量、币种、政策标记、匹配结果、异常列表和证据是唯一事实来源。目标文本只允许复述这些内容。

## 固定拆分

- train: 160
- validation: 20
- test: 20
- 每种顶层异常类型: 25

重新生成：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\generate_anomaly_explanations.py --seed 42
```

生成后应运行 `tests/test_phase3_dataset.py`，并核对 `reports/phase3/dataset_summary.json` 中的 SHA256。
