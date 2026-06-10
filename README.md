# ProcureGuard AI

ProcureGuard AI 是一个企业采购发票智能审核 Agent。当前后端已经完成真实规则链，Phase 1 正在补齐可替换占位字段的模型抽取能力。

## 当前功能

- FastAPI 发票上传、查询和人工审核接口
- SQLite 共享契约、mock 采购订单、收货记录和政策数据
- 5 个 Agent 工具：查 PO、查收货、查重复、查政策、提交人工审核
- 真实规则链写入 ExtractedFields、ValidationResult、AuditReport 和 Audit Trace
- Phase 1A OCR baseline：OCR token 契约、PaddleOCR 可选适配器、SROIE reader、OCR + Regex baseline、字段级 F1、错误分析

## Dataset

- SROIE: ICDAR 2019 competition dataset, public research dataset
- Voxel51/scanned_receipts: Hugging Face 上的 SROIE Task 3 entity metadata
- CORD: Naver Clova AI public dataset on Hugging Face
- Synthetic anomaly samples: planned with reportlab, self-annotated

All public datasets are used for research purposes only.

真实数据请放到 `data/phase1/`，具体目录见 [data/phase1/README.md](/D:/ProcureAgent/data/phase1/README.md)。数据目录默认不提交到 Git。

## Phase 1A OCR Baseline

可选安装 Phase 1 / extraction 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[extraction]"
```

Windows 下 PaddleOCR / PaddlePaddle 可能需要按官方说明选择对应安装包；本项目不在脚本里自动修复本地深度学习环境。

当前 Windows Python 3.13 已验证：

```text
PaddleOCR 3.6.0
PaddlePaddle 3.3.1
Torch 2.12.0
Transformers 4.57.6
```

fixture smoke 闭环：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie.py `
  --input tests/fixtures/sroie_minimal/raw `
  --output tests/fixtures/sroie_minimal/processed.jsonl

.\.venv\Scripts\python.exe scripts/phase1/evaluate_baseline.py `
  --input tests/fixtures/sroie_minimal/processed.jsonl `
  --output reports/phase1/baseline_fixture_report.json `
  --data-source tests/fixtures/sroie_minimal `
  --fixture

.\.venv\Scripts\python.exe scripts/phase1/analyze_errors.py `
  --input reports/phase1/baseline_fixture_report.json `
  --output reports/phase1/baseline_fixture_errors.md
```

真实 SROIE baseline 命令示例：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/organize_sroie_dataset.py `
  --input data/phase1/sroie/inbox/SROIE/unpacked/sroie `
  --output data/phase1/sroie/raw

.\.venv\Scripts\python.exe scripts/phase1/check_sroie_dataset.py `
  --input data/phase1/sroie/raw

.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie.py `
  --input data/phase1/sroie/raw/train `
  --output data/phase1/sroie/processed/train.jsonl

.\.venv\Scripts\python.exe scripts/phase1/evaluate_baseline.py `
  --input data/phase1/sroie/processed/train.jsonl `
  --output reports/phase1/baseline_sroie_train_report.json `
  --data-source sroie_train
```

当前 ModelScope 镜像只包含整图、OCR bbox annotation 和 crop OCR 文本标签。`train_label.jsonl/test_label.jsonl` 的字段只有 `filename/text`，不包含 `company/address/date/total` ground truth。因此当前可以运行真实票据 baseline 预测，但不能计算真实字段级 F1：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie.py `
  --input data/phase1/sroie/raw/test `
  --output data/phase1/sroie/processed/test_unlabeled.jsonl `
  --allow-missing-labels

.\.venv\Scripts\python.exe scripts/phase1/predict_baseline.py `
  --input data/phase1/sroie/processed/test_unlabeled.jsonl `
  --output data/phase1/sroie/processed/test_baseline_predictions.jsonl
```

评测脚本会拒绝对无实体 ground truth 的数据计算 F1。

## Labeled SROIE Task 3

下载带实体标签的数据：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/download_sroie_task3.py `
  --dataset Voxel51/scanned_receipts `
  --output data/phase1/sroie_task3 `
  --local-image-source data/phase1/sroie/raw/train/img `
  --local-image-source data/phase1/sroie/raw/test/img
```

生成固定 seed 的 train/validation：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie_task3.py `
  --input data/phase1/sroie_task3 `
  --output data/phase1/sroie_task3/processed `
  --seed 42
```

本地实际 712 条，拆分为 570 train / 142 validation。评测口径为：

```text
evaluation_split = local_validation_split_seed_42
```

真实 validation baseline 结果：

| field | precision | recall | f1 |
| --- | ---: | ---: | ---: |
| company | 0.5704 | 0.5704 | 0.5704 |
| address | 0.0070 | 0.0070 | 0.0070 |
| date | 0.9808 | 0.7183 | 0.8293 |
| total | 0.3672 | 0.3310 | 0.3481 |
| macro | 0.4814 | 0.4067 | 0.4387 |

Task 3 有效 batch smoke 的 `labels_non_o_count=6`，单 batch forward 在 CPU 上得到 loss `2.216274`。这些是训练前验证，不是 fine-tuned 模型结果。

PaddleOCR 端到端 smoke：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/smoke_paddleocr.py `
  --input data/phase1/sroie/raw/train/img `
  --limit 3
```

LayoutLMv3 Dataset/DataLoader smoke：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/smoke_layoutlmv3_batch.py `
  --input tests/fixtures/sroie_minimal/processed.jsonl `
  --batch-size 1
```

可选单 batch forward：

```powershell
.\.venv\Scripts\python.exe scripts/phase1/smoke_layoutlmv3_forward.py `
  --input tests/fixtures/sroie_minimal/processed.jsonl `
  --batch-size 1
```

SROIE token classification 标签固定为：

```text
O
B-COMPANY / I-COMPANY
B-ADDRESS / I-ADDRESS
B-DATE / I-DATE
B-TOTAL / I-TOTAL
```

训练 Notebook：

```text
notebooks/phase1_layoutlmv3_training.ipynb
```

Notebook 包含手写 PyTorch 训练循环、validation 和 best checkpoint 代码。尚未在真实 SROIE 上运行的指标标记为 `待真实训练`。

限制：

- fixture 分数只是 smoke result，不能作为最终模型效果或简历指标。
- 当前 baseline 只评测 SROIE 的 `company`、`address`、`date`、`total`。
- PaddleOCR 是可选依赖，不进入默认后端运行环境。
- 当前不接入后端 API。
- LayoutLMv3 真实训练指标仍待真实数据和合适 GPU 环境运行。
- 当前 validation 是固定 seed 本地拆分，不是官方 test。
- LayoutLMv3 fine-tuned 字段级 F1 仍为 `待真实训练`。

## 本地测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Phase 1 下一步

- 下载并整理 SROIE/CORD 数据
- 跑 OCR + Regex baseline
- 完成 LayoutLMv3 token 标签对齐和训练循环
- 输出 baseline vs fine-tuned 字段级 F1 对比表
- 整理错误案例分析
