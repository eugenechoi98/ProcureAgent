# Phase 4F.1：LayoutLMv3 Runtime Asset Bundle

## 结论

Runtime bundle 准备脚本与校验契约已经完成。本页记录的是 Phase 4F.1 当时的 blocked 状态；Phase 4F.2 已从本地外部 artifact 找回 `layoutlmv3_best.zip` 并恢复 bundle，见 [Phase 4F.2 artifact recovery](phase4f2_layoutlmv3_artifact_recovery.md)。

## 资产审计

Phase 1 Notebook 的训练代码明确执行：

```text
model.save_pretrained(checkpoints/phase1/layoutlmv3_best)
processor.save_pretrained(checkpoints/phase1/layoutlmv3_best)
```

随后还会生成 `layoutlmv3_best.zip`，供用户从 ModelScope/Colab 手动下载。Phase 1G 的 142 条 validation inference 使用的也是该云端 checkpoint 和 Notebook 当前 Kernel 内加载的 processor/model，而不是当前仓库中的权重。

当前本地审计结果：

| 资产 | 状态 |
|---|---|
| 微调 `model.safetensors` | 未找到 |
| 微调 checkpoint `config.json` | 未找到 |
| 随训练保存的 processor/tokenizer | 未找到 |
| checkpoint 内 `id2label/label2id` | 未找到 |
| `layoutlmv3_best.zip` | 未找到 |
| 公开 `microsoft/layoutlmv3-base` 本地缓存 | 存在，但不是微调 checkpoint |
| Phase 1 BIO 定义 | 存在于 `procureguard.extraction.alignment` |
| 公开 SROIE sample image | 存在 |

Phase 4F checker 原默认路径与 Phase 1 Notebook 输出路径一致，都是 `checkpoints/phase1/layoutlmv3_best`，问题不是路径不一致，而是云端 checkpoint bundle 未回传。

## Bundle 准备脚本

```powershell
.\.venv\Scripts\python.exe scripts\phase4\prepare_layoutlmv3_runtime_assets.py
```

目标目录：

```text
artifacts/phase1_runtime/layoutlmv3_sroie_corrected/
```

该目录受 `.gitignore` 保护。脚本会：

1. 要求真实 `model.safetensors` 和 checkpoint `config.json`。
2. 验证 checkpoint 的 9 个 BIO label 顺序与 Phase 1 代码完全一致。
3. 优先复制 checkpoint 自带 processor；缺失时可通过 `--base-processor` 指向已存在的匹配 base processor 本地目录。
4. 仅在 label order 验证通过后，从 Phase 1 `BIO_LABELS/ID2LABEL/LABEL2ID` 重建 `label_map.json`。
5. 为每个复制或生成的文件记录 size、SHA256 和 source。
6. 不访问网络，不静默下载，不接受 Git tracked 输出路径。

如果 checkpoint 缺失，脚本只生成 `README.md` 和 `runtime_manifest.json`，manifest 状态为 `blocked_missing_checkpoint`，不会复制公开 base model冒充微调结果。

## 恢复命令

拿到 ModelScope/Colab 导出的 `layoutlmv3_best.zip` 后，将其解压到仓库外或 ignored checkpoint 目录，再运行：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\prepare_layoutlmv3_runtime_assets.py `
  --checkpoint checkpoints\phase1\layoutlmv3_best `
  --base-processor .cache\huggingface\hub\models--microsoft--layoutlmv3-base\snapshots\<revision>
```

如果 checkpoint zip 已包含 processor，省略 `--base-processor`。不要重新下载或训练，优先找回原始 zip，以保证权重、config 和 label order 来自同一次训练运行。

## 加强后的资产检查

```powershell
.\.venv\Scripts\python.exe scripts\phase4\check_live_extraction_assets.py `
  --checkpoint artifacts\phase1_runtime\layoutlmv3_sroie_corrected `
  --processor artifacts\phase1_runtime\layoutlmv3_sroie_corrected `
  --label-map artifacts\phase1_runtime\layoutlmv3_sroie_corrected\label_map.json `
  --sample-image demo\e2e_cases\case_a_standard_pass\source_invoice.png
```

Checker 会同时验证 checkpoint、processor、label map、model config label 数量与顺序、sample image、OCR 依赖和 CPU/GPU 策略。它仍然不加载模型、不下载资产。

## 当前边界

- Fake fixture 只验证 bundle/schema/failure contract，不算真实 live extraction。
- 当前没有字段候选摘要或真实延迟，因为微调 checkpoint 不存在。
- 没有调用 Phase 2，也没有生成 `risk_level` 或 `recommended_action`。
- 模型权重没有提交 Git。
- 暂不进入 Phase 4G；进入门槛是用找回的原始微调 bundle 完成至少一次公开图片真实推理。

相关文档：

- [Phase 4F Local Live Extraction](phase4f_local_live_extraction_spike.md)
- [Phase 1 GPU Notebook Runbook](PHASE1_GPU_NOTEBOOK_RUNBOOK.md)
- [隐私与数据边界](PRIVACY_AND_DATA_BOUNDARIES.md)
