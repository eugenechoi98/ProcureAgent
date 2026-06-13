# Model Lab Artifacts

本目录只整理已有真实实验报告，供后续 Portfolio Demo 的 Model Lab 页签读取。

边界：

- 不加载 LayoutLMv3、Qwen 或 LoRA。
- 不包含 checkpoint、adapter、safetensors 或图片副本。
- 不把 validation 指标说成 official test。
- 不把离线实验说成网页实时推理。

展示口径：

- LayoutLMv3: `offline_checkpoint_inference`，`local_validation_split_seed_42`，`official_test=false`。
- LoRA: ModelScope 真实离线实验结果，不是当前 Web 实时推理；第二轮 adapter 未通过上线 hard gate。

入口文件：

- `manifest.json`：总来源、缺失项和展示边界。
- `layoutlmv3/metrics.json`：抽取指标。
- `layoutlmv3/training_curve.json`：训练曲线数据。
- `layoutlmv3/selected_predictions.json`：3 到 5 条真实 checkpoint inference 案例。
- `layoutlmv3/error_analysis.json`：错误来源摘要。
- `lora/metrics.json`：两轮 LoRA 评测结果。
- `lora/training_curves.json`：两轮 loss，缺失处显式为 `null`。
- `lora/hallucination_cases.json`：真实幻觉案例。
- `lora/guard_cases.json`：guard/fallback 展示案例。
