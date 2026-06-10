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
