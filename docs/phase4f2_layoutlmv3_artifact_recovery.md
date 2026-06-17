# Phase 4F.2：LayoutLMv3 Artifact Recovery

## 结论

已找到 `layoutlmv3_best.zip`，并成功恢复本地 runtime bundle：

```text
D:\ProcureAgent_LocalArtifacts\Phase1\layoutlmv3_best.zip
-> artifacts/phase1_runtime/layoutlmv3_sroie_corrected/
```

恢复后的 bundle 通过 asset checker，并完成一次真实本地 live extraction。当前可以进入 Phase 4G 的字段确认与 Phase 2 集成设计，但仍不能跳过人工确认。

## Runtime Bundle

Bundle 包含：

- `model.safetensors`
- `config.json`
- processor / tokenizer / preprocessor 文件
- `label_map.json`
- `runtime_manifest.json`
- `README.md`

`runtime_manifest.json` 记录文件名、size、SHA256 和来源路径。bundle 位于 ignored `artifacts/`，模型权重没有提交 Git。

## Live Extraction Smoke

```text
sample_image=demo/e2e_cases/case_a_standard_pass/source_invoice.png
device=cpu
cuda_available=false
ocr_token_count=40
latency_seconds=203.3415
phase2_invoked=false
risk_action_generated=false
```

字段候选：

| field | predicted value | confidence | human confirmation |
|---|---|---:|---|
| company | Golden Arches Restaurants Sdn Bhd | 0.9032 | required |
| address | Level 6, Bangunan TH, Damansara Uptown3 No.3, Jalan SS21/39,47400 Petaling Jaya Selangor | 0.9014 | required |
| date | 2016-12-25 | 0.9744 | required |
| total | 29.28 | 0.8011 | required |

这些字段是 LayoutLMv3 候选，不是采购风险结论。OCR 或字段错误不能被当作采购异常。

## Rebuild Fallback

本轮不需要重训。若未来 artifact 再次丢失，使用 [rebuild plan](phase4f2_layoutlmv3_rebuild_plan.md)，并且只有用户明确说“允许重训”后，才能执行重训脚本。
