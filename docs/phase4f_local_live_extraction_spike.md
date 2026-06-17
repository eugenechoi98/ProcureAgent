# Phase 4F：Local Live OCR / LayoutLMv3 Extraction Spike

## 当前状态

Phase 4F 的本地资产检查、独立 extraction 入口、字段候选契约和失败契约已经完成。当前工作区缺少 Phase 1 微调 checkpoint 及随 checkpoint 保存的 processor/label map，因此**真实 OCR -> LayoutLMv3 成功推理尚未验收**。

本机存在 Torch、Transformers、Pillow、PaddleOCR 和 PaddlePaddle，且允许 CPU inference；仓库缓存中的 `microsoft/layoutlmv3-base` 只是公开 base model，不能替代已完成离线评测的微调 checkpoint。

## 资产要求

默认 checkpoint 目录：

```text
checkpoints/phase1/layoutlmv3_best/
```

至少需要：

- `model.safetensors`，不允许回退到 `.bin`、`.pt`、`.pth` 或 `.ckpt`。
- `config.json`，其中 `id2label` 包含 Phase 1 的 9 个 BIO 标签。
- `preprocessor_config.json`。
- `tokenizer_config.json`。
- `tokenizer.json`，或 `vocab.json` + `merges.txt`。
- 本地可用的 PaddleOCR/PaddlePaddle 依赖及 OCR 模型缓存。
- 公开、synthetic 或经过确认可用于研究的 PNG/JPEG 图片。

模型权重、processor、OCR cache 和受限制数据不提交 Git，也不会由本轮脚本静默下载。

## 只读资产检查

```powershell
.\.venv\Scripts\python.exe scripts\phase4\check_live_extraction_assets.py `
  --output .tmp\phase4f_asset_check.json
```

检查内容包括 checkpoint、安全权重格式、processor、BIO label map、OCR/模型依赖、CUDA 与 CPU 策略。检查不初始化 PaddleOCR、不加载 LayoutLMv3，也不访问网络。资产不完整时返回 exit code `2` 和 JSON failure summary。

## 运行 extraction spike

恢复完整本地资产后运行：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_live_extraction_spike.py `
  --image <public-or-synthetic-invoice.png> `
  --output-dir .tmp\live_extraction
```

成功输出：

- `ocr_tokens.json`：PaddleOCR token、0-1000 bbox 和 OCR confidence。
- `layoutlmv3_field_candidates.json`：字段值、真实 word-label softmax 均值、token span、bbox、来源和人工确认标记。
- `extraction_report.md`：本地运行摘要、耗时和边界。
- `environment_summary.json`：资产与运行环境摘要。
- `bbox_visualization.png`：可选 OCR/字段预测可视化。

如果字段没有预测 span，`confidence` 为 `null`，不会编造分数。所有字段都标记 `source=live_layoutlmv3` 和 `requires_human_confirmation=true`。

## 失败契约

失败时返回非零 exit code，并生成 `extraction_failure.json`。稳定失败码包括：

- `missing_checkpoint`
- `missing_processor`
- `missing_label_map`
- `ocr_dependency_missing`
- `ocr_no_tokens`
- `image_file_invalid`
- `layoutlmv3_inference_failed`
- `field_reconstruction_failed`
- `unsupported_runtime`
- `no_cuda_and_cpu_disabled`

CPU 允许但没有 CUDA 时，环境摘要记录 `no_cuda_but_cpu_allowed`，不把它当作失败。任何失败都不会生成伪字段预测，也不会继续进入 Phase 2。

## 产品边界

- 当前是本地 extraction spike，不是 FastAPI、工作台或 HF public Demo 功能。
- 不调用 Phase 2，不生成 AuditReport、`risk_level`、`recommended_action` 或 `anomaly_types`。
- OCR 只提供 token、bbox 和 confidence；LayoutLMv3 才生成字段候选。
- 字段必须在 Phase 4G 由用户确认或修正后，才能进入确定性审核链。
- OCR 错误和字段抽取错误不能被当作采购异常。
- 本轮不是 official test，也不能证明企业发票泛化能力。
- 请勿使用真实敏感发票；优先使用 SROIE 公开样例或 synthetic 图片。

## 下一步门槛

暂不进入 Phase 4G。先恢复与 Phase 1 离线结果对应的完整微调 checkpoint，使用公开样例完成至少一次真实 OCR + LayoutLMv3 本地推理，并记录设备、单次延迟、字段候选和失败状态。完成该门槛后，再设计 field confirmation 与 Phase 2 integration。

Phase 4F.2 已从本地外部 [artifact recovery](phase4f2_layoutlmv3_artifact_recovery.md) 找回 `layoutlmv3_best.zip`，恢复 runtime bundle，并完成一次 CPU live extraction。下一步是 Phase 4G 字段确认门，而不是直接进入 Phase 2 风险判断。

相关文档：

- [Phase 4E MVP 架构纠偏](phase4e_product_mvp_architecture_realignment.md)
- [Phase 1 GPU Notebook Runbook](PHASE1_GPU_NOTEBOOK_RUNBOOK.md)
- [隐私与数据边界](PRIVACY_AND_DATA_BOUNDARIES.md)
- [项目架构](../ARCHITECTURE.md)
