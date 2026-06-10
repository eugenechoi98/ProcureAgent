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

可选安装 Phase 1 依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[phase1]"
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
.\.venv\Scripts\python.exe scripts/phase1/prepare_sroie.py `
  --input data/phase1/sroie/raw/train `
  --output data/phase1/sroie/processed/train.jsonl

.\.venv\Scripts\python.exe scripts/phase1/evaluate_baseline.py `
  --input data/phase1/sroie/processed/train.jsonl `
  --output reports/phase1/baseline_sroie_train_report.json `
  --data-source sroie_train
```

限制：

- fixture 分数只是 smoke result，不能作为最终模型效果或简历指标。
- 当前 baseline 只评测 SROIE 的 `company`、`address`、`date`、`total`。
- PaddleOCR 是可选依赖，不进入默认后端运行环境。
- 本轮不接入后端 API，不开始 LayoutLMv3 正式训练。

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
