# ProcureGuard AI

ProcureGuard AI 是一个企业采购发票智能审核 Agent。Phase 1、Phase 2、Phase 3H、Model Lab 轻量 artifacts、Unified Gradio Demo 本地初版和 Hugging Face Spaces 本地发布包初版已完成。

## 当前功能

- FastAPI 发票上传、查询和人工审核接口
- SQLite 共享契约、mock 采购订单、收货记录和政策数据
- 5 个 Agent 工具：查 PO、查收货、查重复、查政策、提交人工审核
- 真实规则链写入 ExtractedFields、ValidationResult、AuditReport 和 Audit Trace
- Phase 1A OCR baseline：OCR token 契约、PaddleOCR 可选适配器、SROIE reader、OCR + Regex baseline、字段级 F1、错误分析
- Phase 3 异常说明：独立数据契约、200 条 synthetic 数据、统一质量评测、Qwen2.5-0.5B-Instruct LoRA Notebook 和两轮真实评测复盘
- Phase 3F Gold Answer 约束：固定章节、缺失字段显式写未提供/缺失、禁止补全未知 PO/GRN/金额/供应商/异常类型
- Phase 3H 受控解释层：Canonical Audit Facts 适配、确定性模板、受控改写契约、LoRA 输出 guard、fallback orchestrator 和 audit trail
- Model Lab 轻量 artifacts：整理 LayoutLMv3 与两轮 LoRA 的真实离线指标、曲线、预测案例、幻觉案例和缺失项说明，见 [demo/model_lab/README.md](/D:/ProcureAgent/demo/model_lab/README.md)
- Unified Gradio Demo：本地三页签 `Invoice Audit / Model Lab / Architecture`，保留 Invoice Audit 稳定实时路径，Model Lab 仅读取离线 artifacts，Architecture 解释治理边界
- Hugging Face Spaces 本地发布包：`spaces/procureguard_demo/`，CPU-only、无模型权重、无 GPU requirements、无本地数据库，部署流程见 [docs/HF_SPACES_DEPLOYMENT.md](/D:/ProcureAgent/docs/HF_SPACES_DEPLOYMENT.md)

## 当前 Batch B 状态

Unified Gradio Demo 已在本地完成，包含 Invoice Audit、Model Lab、Architecture 三个页签。Model Lab 读取真实离线轻量 artifacts。当前没有网页实时 LayoutLMv3，没有网页实时真实 LoRA，没有部署 Hugging Face Space。下一步等待总控验收后进入 Batch C。

## 当前 Batch C.1 状态

Batch C.1 已完成本地发布包准备。当前只生成并验证 `spaces/procureguard_demo/`，没有创建 Hugging Face Space，没有登录 Hugging Face，没有上传代码，没有上传模型。Batch C.2 网页端创建 Space 和 Batch C.3 上传验证尚未执行。

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
.\.venv\Scripts\python.exe -m pytest tests\test_phase3h_guarded_explanation.py
```

训练入口：`notebooks/phase3_lora_explainer_training.ipynb`。GPU 依赖单独放在 `requirements/phase3-lora.txt`，不进入默认 FastAPI 环境。运行说明见 [PHASE3_LORA_NOTEBOOK_RUNBOOK.md](docs/PHASE3_LORA_NOTEBOOK_RUNBOOK.md)。

当前已完成两轮 LoRA 真实训练与复盘。第二轮唯一变量为 Phase 3F 事实约束型 Prompt 与统一结构化 Gold Answer，训练参数、模型、split 和评测器均未改变。

第二轮 fine-tuned test 结果：

| metric | value | gate |
| --- | ---: | ---: |
| format_compliance | 0.0000 | >= 0.9000 |
| factual_consistency | 0.9000 | >= 0.9500 |
| action_consistency | 0.4500 | >= 0.9000 |
| anomaly_coverage | 0.4250 | >= 0.9000 |
| hallucination_rate | 0.1500 | <= 0.0500 |

结论：第二轮 adapter 未通过 hard gate，不接 API，不作为默认用户输出。Phase 3H 改为受控解释层：MVP 官方输出使用确定性模板，LoRA 只保留为 shadow/experimental controlled rewrite。

Phase 3H 架构说明见 [PHASE3H_GUARDED_EXPLANATION_ARCHITECTURE.md](docs/PHASE3H_GUARDED_EXPLANATION_ARCHITECTURE.md)。

Phase 3H 核心组件位于 `procureguard/phase3/explanation/`，保持独立并在 Phase 2 风险与动作确定后进行 additive API 接入，不修改 Phase 1、Phase 2 决策逻辑或数据库 schema，也不启动 GPU。默认 `FallbackOrchestrator.explain()` 返回确定性模板；只有显式 `experimental` 且 guard 通过时才可使用 controlled rewrite，`shadow` 模式始终记录模型原文但返回模板。

Phase 3H.1a 已将 Canonical Audit Facts 改为递归不可变快照，并让 rewrite 运行、解析或 guard 异常统一 fail-closed 回退模板。当前 guard 是保守的结构化规则 guard，不是生产级语义校验器；它不能证明自然语言语义完全等价，也不能完全消除同义改写、隐含推断或未建模实体带来的风险。MVP 默认输出仍是确定性模板，LoRA 仍只允许 shadow 或 experimental 使用。

Phase 3H.2 已把受控解释层最小接入真实审核报告。上传接口新增可选 `explanation_mode=template|shadow|experimental`，默认 `template`，无需模型、网络或 GPU。`AuditReport.explanation` 是 additive 字段，保留旧字段语义；解释 trace 随 audit report JSON 返回，不修改数据库 schema。shadow/experimental 仅支持显式注入 provider，当前项目没有配置真实 LoRA provider。

Phase 3H.3 增加 13 个固定离线 Demo Cases 和端到端测试，覆盖正常发票、缺少 PO/GRN、供应商不一致、金额不一致、重复发票、多异常、高风险模板回退、shadow trace、experimental guard pass/fail、provider 异常和非法输出。运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_phase3h_integration.py tests\test_phase3h_demo_cases.py -q
```

当前没有启动真实 LoRA 推理，没有默认 API 模型依赖，没有第三次训练，没有 HF Spaces，也没有 LangChain 对比实验。

Phase 3H 与 Local Gradio Demo Baseline 已合并到 `main`。当前本地 readiness 只代表离线演示准备情况，不代表线上部署通过。首次公开 Demo 推荐优先使用固定或预生成 `ExtractedFields` 的混合模式，固定样例作为 fallback；完整在线 LayoutLMv3 和真实 LoRA 暂不作为首次部署 blocker。评估见 [DEMO_DEPLOYABILITY_REVIEW.md](docs/DEMO_DEPLOYABILITY_REVIEW.md)。

本地只读 readiness：

```powershell
.\.venv\Scripts\python.exe scripts\demo\verify_demo_readiness.py
```

脚本默认只打印 JSON，不启动服务、不加载模型、不访问网络，也不写文件。

## Local Gradio Demo

当前已完成本地离线 Gradio Demo。默认使用混合模式：预生成 `ExtractedFields` 实时运行 Phase 2、Canonical Facts、确定性模板和 AuditReport；无法由现有 Phase 2 fixture 精确复现的场景明确进入固定样例 fallback。

安装与启动：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -e ".[demo]"
.\.venv\Scripts\python.exe -m demo.app
```

默认 FastAPI 后端使用第一条命令，不安装 Gradio；本地 Demo 需要显式安装 `.[demo]`，其中固定使用已验证的 `gradio==5.50.0`。本地地址：`http://127.0.0.1:7860`。当前完成的是本地离线 Demo，没有创建 Hugging Face Space；默认不 share、不创建公网链接、不需要 API Key 或 GPU。shadow 和 experimental 只使用 fake provider，不加载 Qwen、真实 LoRA 或在线 LayoutLMv3。详细说明见 [LOCAL_GRADIO_DEMO.md](docs/LOCAL_GRADIO_DEMO.md)。

## Portfolio Demo Roadmap

统一 Portfolio Demo 设计已经冻结为三个页签：

1. **Invoice Audit**：保留当前稳定混合模式，实时运行 Phase 2、Policy RAG、Risk Engine、Canonical Facts、Template/Guard/Fallback 和 AuditReport。
2. **Model Lab**：后续展示 LayoutLMv3 与两轮 LoRA 的真实离线指标、loss、预测案例、错误分析和 artifacts 来源。
3. **Architecture**：展示模型抽取、5 个 Agent 工具、三单匹配、Policy RAG、Risk Engine 和受控解释层的边界。

当前状态必须按以下口径理解：

- 本地稳定 Gradio Demo Baseline 已完成。
- 三页签设计已冻结，但 Model Lab 尚未实现。
- Hugging Face Spaces 尚未部署。
- LangChain Policy RAG 对比尚未开始。
- Docker Compose 与 GitHub Actions CI 尚待工程交付收口。
- 在线 LayoutLMv3 与真实 LoRA 推理均未启用；现阶段优先展示真实离线 artifacts。

完整设计见 [PORTFOLIO_DEMO_DESIGN.md](docs/PORTFOLIO_DEMO_DESIGN.md)。

Phase 3B 环境检查入口：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\verify_lora_notebook_env.py
.\.venv\Scripts\python.exe scripts\phase3\bootstrap_lora_notebook.py
.\.venv\Scripts\python.exe scripts\phase3\base_inference_smoke.py
```

## Phase 1 状态

Phase 1 已完成数据处理、OCR baseline、LayoutLMv3 微调、字段级 F1、日期错误分析
和 checkpoint inference 证据封板。模型抽取仍保持离线，尚未替换 API 占位字段。
