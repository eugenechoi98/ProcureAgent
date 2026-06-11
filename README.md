# ProcureGuard AI

ProcureGuard AI 是一个企业采购发票智能审核 Agent。Phase 1 模型抽取与 Phase 2 确定性审核链已封板，当前进入 Phase 3 异常说明 LoRA 数据与训练骨架阶段。

## 当前功能

- FastAPI 发票上传、查询和人工审核接口
- SQLite 共享契约、mock 采购订单、收货记录和政策数据
- 5 个 Agent 工具：查 PO、查收货、查重复、查政策、提交人工审核
- 真实规则链写入 ExtractedFields、ValidationResult、AuditReport 和 Audit Trace
- Phase 1A OCR baseline：OCR token 契约、PaddleOCR 可选适配器、SROIE reader、OCR + Regex baseline、字段级 F1、错误分析
- Phase 3A 异常说明：独立数据契约、200 条 synthetic 数据、统一质量评测和 Qwen2.5-0.5B-Instruct LoRA Notebook 骨架
- Phase 3B Notebook guard：bootstrap、verify、runtime context、数据 SHA 校验、模型目录 guard 和 base inference smoke dry-run

## Dataset

- SROIE: ICDAR 2019 competition dataset, public research dataset
- Voxel51/scanned_receipts: Hugging Face 上的 SROIE Task 3 entity metadata
- CORD: Naver Clova AI public dataset on Hugging Face
- Synthetic anomaly explanations: 200 programmatically generated samples with fixed seed 42

All public datasets are used for research purposes only.

真实数据请放到 `data/phase1/`，具体目录见 [data/phase1/README.md](/D:/ProcureAgent/data/phase1/README.md)。数据目录默认不提交到 Git。

Phase 3 可提交数据全部为 synthetic，说明见 [data/phase3/README.md](data/phase3/README.md)。固定拆分为 160 train / 20 validation / 20 test，每种顶层异常类型 25 条。

## Phase 1 Dataset And Baseline

Phase 1 使用带实体标签的 `Voxel51/scanned_receipts` Task 3 数据。

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

Task 3 数据整理、OCR baseline、BIO alignment、PaddleOCR smoke 和 LayoutLMv3 GPU 微调均已完成。

## GPU Fine-tuning Notebook

训练入口：

```text
notebooks/phase1_layoutlmv3_training.ipynb
```

Notebook 首个代码单元统一运行 GPU bootstrap，支持：

```python
RUNTIME = "modelscope"  # 或 "colab"
```

默认参数：

```text
model: microsoft/layoutlmv3-base
max_length: 512
batch_size: 2
gradient_accumulation_steps: 4
epochs: 5
learning_rate: 1e-5
weight_decay: 0.01
max_grad_norm: 1.0
seed: 42
```

GPU 环境固定规则：

- 所有依赖安装使用 Notebook Kernel 的 `sys.executable`。
- Terminal Python 与 Kernel 不一致时，以 Kernel 为训练真源。
- 模型默认从本地目录加载，并使用 `local_files_only=True`。
- bootstrap 自动备份并修复 processed JSONL 图片路径。
- hydrate 在当前 Kernel 一次性恢复 BIO 标签、样本、processor、Torch 和 device。
- 只有 `training_guard_passed=true` 且 `missing_names=[]` 才进入训练。

环境文件：

```text
requirements/phase1-gpu.txt
scripts/phase1/bootstrap_gpu_notebook.py
scripts/phase1/verify_gpu_notebook_env.py
procureguard/extraction/gpu_notebook_context.py
```

Notebook 包含手写 PyTorch train/validation loop、token/field F1、best checkpoint、loss PNG，以及 JSON/CSV/Markdown 训练报告导出。

运行手册：

[docs/PHASE1_GPU_NOTEBOOK_RUNBOOK.md](docs/PHASE1_GPU_NOTEBOOK_RUNBOOK.md)

完整 fine-tuning 已执行，结果见下方 First GPU Fine-tuning Run。该结果来自固定本地 validation，不是 official test。

### First GPU Fine-tuning Run

首次完整 GPU 微调已在 NVIDIA A10 上完成：

```text
evaluation_split = local_validation_split_seed_42
official_test = false
epochs = 5
batch_size = 2
gradient_accumulation_steps = 4
learning_rate = 1e-5
best_epoch = 5
token_f1 = 0.8647
field_macro_f1 = 0.6231
baseline_macro_f1 = 0.4387
improvement = 0.1844
```

字段 F1：

| field | Regex baseline | 首轮 LayoutLMv3 | Corrected LayoutLMv3 | Hybrid |
| --- | ---: | ---: | ---: | ---: |
| company | 0.5704 | 0.7068 | 0.7068 | 0.7068 |
| address | 0.0070 | 0.7376 | 0.7376 | 0.7376 |
| date | 0.8293 | 0.1423 | 0.8764 | 0.8293 |
| total | 0.3481 | 0.9058 | 0.9058 | 0.9058 |
| macro | 0.4387 | 0.6231 | 0.8067 | 0.7949 |

现有 checkpoint 在同一 142 条 validation 上完成离线推理。日期重建清洗使 date F1
从 0.1423 提升到 0.8764，`date_f1_recovery=+0.7341`；corrected pure
LayoutLMv3 macro F1=0.8067，高于 Hybrid macro F1=0.7949。因此 Phase 1 MVP
推荐 `pure_layoutlmv3_date_path`，Hybrid 只保留为 fallback 思路。

该结果属于 `offline_checkpoint_inference` 和
`local_validation_split_seed_42`，不是 official test，尚未接入 API。

训练报告见 [reports/phase1/gpu_training](reports/phase1/gpu_training)，日期专项分析见
[layoutlmv3_date_error_analysis.md](reports/phase1/layoutlmv3_date_error_analysis.md)，
checkpoint inference 证据见
[reports/phase1/checkpoint_inference](reports/phase1/checkpoint_inference)。

SROIE token classification 标签固定为：

```text
O
B-COMPANY / I-COMPANY
B-ADDRESS / I-ADDRESS
B-DATE / I-DATE
B-TOTAL / I-TOTAL
```

限制：

- fixture 分数只是 smoke result，不能作为最终模型效果或简历指标。
- 当前 baseline 只评测 SROIE 的 `company`、`address`、`date`、`total`。
- PaddleOCR 是可选依赖，不进入默认后端运行环境。
- 当前不接入后端 API。
- 当前 validation 是固定 seed 本地拆分，不是官方 test。

## 本地测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Phase 3 LoRA Anomaly Explainer

Phase 3 小模型只把确定性规则链已经产生的异常事实整理成审核说明。它不计算金额、不决定 `risk_level`，也不改变 `recommended_action`。

生成数据与运行专项测试：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\generate_anomaly_explanations.py --seed 42
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_dataset.py tests\test_phase3_evaluation.py
```

训练入口：`notebooks/phase3_lora_explainer_training.ipynb`。GPU 依赖单独放在 `requirements/phase3-lora.txt`，不进入默认 FastAPI 环境。运行说明见 [PHASE3_LORA_NOTEBOOK_RUNBOOK.md](docs/PHASE3_LORA_NOTEBOOK_RUNBOOK.md)。

当前已完成 Notebook 可复现 guard 和 base inference dry-run 入口，尚未执行 LoRA GPU 训练，也没有 fine-tuned 真实指标。

Phase 3B 环境检查入口：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\verify_lora_notebook_env.py
.\.venv\Scripts\python.exe scripts\phase3\bootstrap_lora_notebook.py
.\.venv\Scripts\python.exe scripts\phase3\base_inference_smoke.py
```

## Phase 1 状态

Phase 1 已完成数据处理、OCR baseline、LayoutLMv3 微调、字段级 F1、日期错误分析
和 checkpoint inference 证据封板。模型抽取仍保持离线，尚未替换 API 占位字段。
