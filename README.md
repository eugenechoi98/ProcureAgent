# ProcureGuard AI

**ProcureGuard AI：受控采购发票审核 Agent**

ProcureGuard AI 是一个开源可运行的采购发票审核 MVP。它把发票字段、PO/GRN mock context、政策规则和风险引擎串成可审计的 `AuditReport`，并严格限制模型的职责：模型可以抽字段或润色解释，但不能决定风险等级或建议动作。

## 30 秒系统地图

### Path A：Fast Path / Product Entry

```text
Manual invoice fields
-> explicit mock PO/GRN context
-> deterministic audit engine
-> AuditReport JSON / Markdown
```

- **用途**：本地 product-like demo 和开源 Quickstart 的主入口。
- **特点**：不运行 ML、不下载模型、无 GPU、几秒内返回结果。
- **边界**：PO/GRN 是显式 mock context，不是企业 ERP；AuditReport 不是付款凭证。

### Path B：AI Vision Path / Research Demo

```text
Invoice image
-> OCR tokens + bbox
-> LayoutLMv3 field candidates
-> human confirmation
-> deterministic audit engine
-> AuditReport
```

- **用途**：展示发票图片到字段候选的 AI vision 能力。
- **特点**：CPU-only 本地 live inference 约 **3 分钟 / 张**，用于 research/demo。
- **边界**：LayoutLMv3 只生成 candidate，不是最终事实；字段必须确认后才进入审核。公网 Hugging Face Demo 当前不支持任意发票上传并在线跑 LayoutLMv3。

### System Core：Deterministic Audit + Guarded Explanation

- 三单匹配、重复检测、Policy RAG 和 Risk Engine 是正式审核核心。
- `risk_level` 和 `recommended_action` 只由确定性规则生成。
- LoRA 只用于 experimental / guarded explanation rewrite：Guard PASS 才能展示改写文本，Guard FAIL 或 provider unavailable 会 fallback deterministic template。

## Live Demo

[Hugging Face Space](https://huggingface.co/spaces/eugene-98/procureguard-ai-demo)

CPU-only 公网 Demo，不需要 API Key、GPU 或模型下载。
当前页面不支持上传任意发票并现场运行 LayoutLMv3；主入口展示已验收的
端到端离线模型证据，以及轻量 CPU 审核规则链。

> **安全边界**：本项目是研究原型和作品集 Demo，不是生产财务系统，不可作为付款依据。请勿上传真实敏感发票。详见 [隐私与数据边界](docs/PRIVACY_AND_DATA_BOUNDARIES.md)。

## Quick Start：2 Steps

要求 Python 3.10+，推荐 Python 3.11。下面命令使用 Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[demo,test]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip check
```

`.env.example` 中的 `DATABASE_PATH=data/procureguard.db` 和 `UPLOAD_DIR=uploads` 只适合本地 Demo。FastAPI 首次启动时会自动创建 SQLite schema 和 mock 数据；当前应用不自动加载 dotenv，需要覆盖路径时请在 PowerShell 显式设置环境变量。

### Step 1：Run Manual Audit

```powershell
.\.venv\Scripts\python.exe scripts\samples\run_sample_audit.py
```

这是 Path A：使用 synthetic 发票字段和 mock PO/GRN，输出 AuditReport JSON。它不运行 OCR/LayoutLMv3、LoRA 或网络请求。

### Step 2：Run Sample API

```powershell
.\.venv\Scripts\python.exe -m uvicorn procureguard.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
$body = Get-Content -Raw -Encoding UTF8 samples\manual_audit\request_standard_pass.json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/mvp/manual-audit -ContentType "application/json" -Body $body
```

打开 `http://127.0.0.1:8000/docs` 查看 OpenAPI，健康检查为 `http://127.0.0.1:8000/health`。完整 clean-clone、分层测试和发布检查见 [Open-source Quickstart](docs/OPEN_SOURCE_QUICKSTART.md)，样例说明见 [samples/README.md](samples/README.md)。

本地 Gradio Demo 可选启动：

```powershell
.\.venv\Scripts\python.exe -m demo.app
```

打开 `http://127.0.0.1:7860`。

### Optional Local Extraction Spike

Phase 4F 提供独立的本地 OCR/LayoutLMv3 资产检查和 extraction spike，不接 API、Phase 2 或 HF Demo：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\check_live_extraction_assets.py
```

当前仓库不提交 Phase 1 微调 checkpoint，clean clone 预期会明确返回缺资产状态，不会下载模型或伪造预测。完整资产和运行命令见 [Phase 4F 说明](docs/phase4f_local_live_extraction_spike.md)。

### Field Confirmation

Phase 4G 新增最小字段确认 API：

```text
POST /api/fields/confirm
```

LayoutLMv3 输出只是 candidate。`invoice_number`、`vendor_name`、`invoice_date` 和 `total_amount` 必须人工确认或修正后，才可形成后续 Phase 2 使用的 `confirmed_fields`。该 API 不生成风险等级或建议动作。

### End-to-End MVP API

Phase 4G-EXT 新增统一端到端入口：

```text
POST /api/mvp/audit/execute
```

它支持 image、field candidates 或 confirmed fields 输入，统一输出 AuditReport JSON、Markdown 和 trace。Phase 2 仍只接收 confirmed fields；风险等级和建议动作仍来自 deterministic rules。

解释层默认使用 `template`。可显式请求 `guarded_lora`，但 clean clone 当前没有真实 LoRA adapter；provider 不可用、Guard 失败、空输出或解析失败都会 fallback deterministic template，并在 trace 中记录原因。LoRA 不会改变风险等级、建议动作或异常类型。

### Manual Audit MVP

启动 FastAPI 后，可用手动字段和显式 mock PO/GRN 运行现有确定性审核链：

```powershell
$body = Get-Content -Raw -Encoding UTF8 samples\manual_audit\request_standard_pass.json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/mvp/manual-audit -ContentType "application/json" -Body $body
```

无需启动 API 的三场景 smoke：

```powershell
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case all
```

这是 `manual_input + explicit_mock_context`，不是在线图片识别或真实企业采购数据。风险等级和建议动作来自 deterministic rules，解释使用 deterministic template，系统没有付款权限。详见 [Phase 4C 说明](docs/phase4c_user_facing_mvp_input_flow.md)。

### Audit Export And Human Review

Manual Audit API 结果在当前服务进程内保存，可进入本地 review queue，并导出 JSON/Markdown：

```text
GET  /api/mvp/manual-audit/review-queue
POST /api/mvp/manual-audit/{audit_id}/review
GET  /api/mvp/manual-audit/{audit_id}/export?format=json
GET  /api/mvp/manual-audit/{audit_id}/export?format=markdown
```

review 支持 `approve`、`reject`、`request_more_info` 和 reviewer note，但不会改写规则产生的风险等级或建议动作。store 在服务重启后清空，导出不是付款凭证，人工决定也不代表企业真实审批。详见 [Phase 4D 说明](docs/phase4d_audit_report_export_review_ux.md)。

## 关键成果

| 方向 | 结果 |
| --- | --- |
| LayoutLMv3 字段抽取 | OCR + Regex baseline Macro F1 `0.4387`；修复后 LayoutLMv3 Macro F1 `0.8067`；Date F1 `0.1423 -> 0.8764` |
| LoRA 异常解释 | 完成两轮 Qwen2.5-0.5B QLoRA 训练；第二轮未通过 hard gate；发现事实幻觉与动作一致性风险；当前回退到确定性模板 |
| 受控生成 | Phase 4H 支持 `template / guarded_lora / shadow_lora`；Guard 拒绝未知单号、金额、日期、供应商、政策或审批角色；Fallback 保证模型不能篡改风险等级、建议动作或异常类型 |
| 工程交付 | Unified Gradio Demo、Hugging Face Space、Docker Compose、GitHub Actions CI、LangChain Policy RAG 对比、Release Readiness |

LoRA 当前不是默认正式解释器，也没有被永久废弃。它保留为 `guarded_lora / shadow_lora` 的受控 rewrite candidate；真实 adapter runtime 尚未接入 clean clone。

## Demo 怎么看

1. 进入“发票审核”，先看案例 A/B 的真实 SROIE validation 图片、OCR bbox、LayoutLMv3 离线 checkpoint prediction、字段 JSON 和 Phase 2 审核结果。
2. A/B 的 PO/GRN 是 mock 采购上下文，用于让真实抽取字段进入三单匹配、Policy RAG 和风险规则链，不是企业真实系统数据。
3. 查看案例 C，理解真实离线 LoRA artifact 为什么不能直接上线，以及 Guard 如何拒绝 `GRN-20260149` 并 fallback 到确定性模板。
4. 进入“模型实验”，查看数据集级 LayoutLMv3 Macro F1、Date F1 和 LoRA hard gate；单个网页案例不用于证明整体指标。
5. 进入“系统架构”，理解为什么模型负责抽取和受控解释，而风险等级与建议动作由确定性规则生成。

详细操作见 [Demo Walkthrough](docs/DEMO_WALKTHROUGH.md)。

## 为什么不是完全自主 LLM Agent？

采购和财务审核是高风险业务场景，金额匹配、三单校验、重复发票检测和审批阈值必须可复现、可审计。因此 ProcureGuard AI 不让 LLM 决定风险等级或建议动作。模型负责字段抽取和受控解释，工具链负责证据查询，最终风险等级和建议动作由确定性规则生成。

**Why not a fully autonomous LLM agent?** Procurement and financial review require reproducible calculations, traceable evidence, and deterministic approval thresholds. ProcureGuard AI therefore keeps field extraction and controlled language generation in the model layer, evidence retrieval in the tool layer, and final risk levels and recommended actions in a deterministic rules engine. The LLM does not choose payment outcomes or invent freedom in a workflow whose tool dependencies are fixed by the business process.

## 当前功能

- FastAPI 发票上传、查询和人工审核接口
- FastAPI Manual Audit MVP：手动字段 + 显式 mock PO/GRN + 确定性 AuditReport
- SQLite 共享契约、mock 采购订单、收货记录和政策数据
- 5 个 Agent 工具：查 PO、查收货、查重复、查政策、提交人工审核
- 真实规则链写入 ExtractedFields、ValidationResult、AuditReport 和 Audit Trace
- Phase 1A OCR baseline：OCR token 契约、PaddleOCR 可选适配器、SROIE reader、OCR + Regex baseline、字段级 F1、错误分析
- Phase 3 异常说明：独立数据契约、200 条 synthetic 数据、统一质量评测、Qwen2.5-0.5B-Instruct LoRA Notebook 和两轮真实评测复盘
- Phase 3F Gold Answer 约束：固定章节、缺失字段显式写未提供/缺失、禁止补全未知 PO/GRN/金额/供应商/异常类型
- Phase 3H 受控解释层：Canonical Audit Facts 适配、确定性模板、受控改写契约、LoRA 输出 guard、fallback orchestrator 和 audit trail
- Phase 4H Guarded LoRA runtime：新增产品模式名、provider unavailable fallback、Guard violation details、解释 trace hash 和 4G-EXT 接入
- Model Lab 轻量 artifacts：整理 LayoutLMv3 与两轮 LoRA 的真实离线指标、曲线、预测案例、幻觉案例和缺失项说明，见 [demo/model_lab/README.md](demo/model_lab/README.md)
- Unified Gradio Demo：保留“发票审核 / 模型实验 / 系统架构”三页签；发票审核页主视图接入 3 个 H0 真实证据链案例，5 个合成流程案例收进补充折叠区
- Hugging Face Spaces 本地发布包：`spaces/procureguard_demo/`，CPU-only、无模型权重、无 GPU requirements、无本地数据库，部署流程见 [docs/HF_SPACES_DEPLOYMENT.md](docs/HF_SPACES_DEPLOYMENT.md)
- Hugging Face 公网 Demo：[Hub](https://huggingface.co/spaces/eugene-98/procureguard-ai-demo) / [App](https://eugene-98-procureguard-ai-demo.hf.space)，发票审核案例故事线与模型实验离线证据均已公开
- LangChain Policy RAG 兼容实验：8 条本地 fixture 的真实离线对比，现有 SQLite FTS5 / BM25 仍是正式主链
- Docker Compose：CPU-only API 与 Unified Demo 双服务配置；当前环境没有 Docker CLI，runtime 尚未验证
- GitHub Actions：CPU-only 依赖、离线 smoke、专项测试、release readiness 和全量测试

## 当前 Batch B 状态

Unified Gradio Demo 已在本地与 Hugging Face Spaces 公开部署，包含“发票审核 / 模型实验 / 系统架构”三个中文页签。发票审核页读取 H0 已验收证据包，模型实验页读取真实离线轻量 artifacts。当前没有网页实时 LayoutLMv3，也没有网页实时真实 LoRA。

三个主案例的证据边界如下：

- 案例 A/B：SROIE validation 图片、OCR bbox、真实离线 LayoutLMv3 checkpoint prediction，以及已验证的 Phase 2 审核结果。
- 案例 A/B 的 PO/GRN：mock 采购上下文，不冒充图片抽取字段或企业真实系统数据。
- 案例 C：真实离线 LoRA artifact、真实 Guard 检测结果和确定性模板 fallback。
- 原 5 个合成案例：只补充展示审核流程分支，不是主模型证据链。

## 当前 Batch C.1 状态

Batch C.1 本地发布包、Batch C.2 Space 创建和 Batch C.3 受控上传均已完成。Space 在 `cpu-basic` 上运行，HTTP、Gradio config、公开 `run_audit` API 和用户人工浏览器验收均已通过。

## Dataset

- SROIE: ICDAR 2019 competition dataset, public research dataset
- Voxel51/scanned_receipts: Hugging Face 上的 SROIE Task 3 entity metadata
- CORD: Naver Clova AI public dataset on Hugging Face
- Synthetic anomaly explanations: 200 programmatically generated samples with fixed seed 42

All public datasets are used for research purposes only.

代码使用 [MIT License](LICENSE)。SROIE、Voxel51 `scanned_receipts`、CORD、基础模型及其衍生资产仍受各自原始许可约束。模型权重、checkpoint、LoRA adapter、缓存、原始训练 artifacts 和受限制数据集不提交 Git；完整边界见 [隐私与数据边界](docs/PRIVACY_AND_DATA_BOUNDARIES.md)。

真实数据请放到 `data/phase1/`，具体目录见 [data/phase1/README.md](data/phase1/README.md)。数据目录默认不提交到 Git。

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
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
```

分层入口：smoke、phase1、phase2、phase3 和 CPU-only full test 见 [Open-source Quickstart](docs/OPEN_SOURCE_QUICKSTART.md)。默认 full test 不下载模型、不运行 GPU Notebook 或 live inference。

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

当前没有启动真实 LoRA 推理，没有默认 API 模型依赖，也没有第三次训练。Hugging Face Space 只运行 CPU-only Unified Demo；LangChain 仅作为离线可选兼容实验，不替换正式 Policy RAG 主链。

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

默认 FastAPI 后端使用第一条命令，不安装 Gradio；本地 Demo 需要显式安装 `.[demo]`，其中固定使用已验证的 `gradio==5.50.0`。本地地址：`http://127.0.0.1:7860`。本地运行默认不 share；公网 Space 同样不需要 API Key 或 GPU。shadow 和 experimental 只使用 fake provider，不加载 Qwen、真实 LoRA 或在线 LayoutLMv3。详细说明见 [LOCAL_GRADIO_DEMO.md](docs/LOCAL_GRADIO_DEMO.md)。

## Portfolio Demo Roadmap

统一 Portfolio Demo 设计已经冻结为三个页签：

1. **Invoice Audit**：保留当前稳定混合模式，实时运行 Phase 2、Policy RAG、Risk Engine、Canonical Facts、Template/Guard/Fallback 和 AuditReport。
2. **Model Lab**：展示 LayoutLMv3 与两轮 LoRA 的真实离线指标、loss、预测案例、错误分析和 artifacts 来源。
3. **Architecture**：展示模型抽取、5 个 Agent 工具、三单匹配、Policy RAG、Risk Engine 和受控解释层的边界。

当前状态必须按以下口径理解：

- 本地稳定 Gradio Demo Baseline 已完成。
- 三页签 Unified Demo 和 Model Lab 已完成本地离线实现。
- Hugging Face Spaces CPU-only Unified Demo 已公开部署并通过用户人工浏览器验收。
- 发票审核页主视图展示 3 个 H0 证据链案例；5 个合成流程案例保留在折叠补充区。单图案例不作为 LayoutLMv3 数据集级 F1 证明。
- LangChain Policy RAG 离线兼容 benchmark 已完成，SQLite FTS5 / BM25 保持正式主链。
- Docker Compose 配置与 GitHub Actions CI 已完成；Docker runtime 尚未在当前环境验证。
- 在线 LayoutLMv3 与真实 LoRA 推理均未启用；现阶段优先展示真实离线 artifacts。

完整设计见 [PORTFOLIO_DEMO_DESIGN.md](docs/PORTFOLIO_DEMO_DESIGN.md)。

## Engineering Delivery

安装完整 CPU-only 验证依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo,langchain,test]"
```

运行本地 release readiness：

```powershell
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
```

默认 readiness 仍是离线聚合，但会读取真实部署报告：Space 已创建并上传，且用户人工浏览器验收已通过，`online_deployment_verified=true`。Docker config ready，但当前环境没有 Docker CLI，因此 Docker runtime not verified。详细步骤见 [ENGINEERING_DELIVERY.md](docs/ENGINEERING_DELIVERY.md)、[HF_SPACES_DEPLOYMENT.md](docs/HF_SPACES_DEPLOYMENT.md) 和 [LANGCHAIN_POLICY_RAG_COMPARISON.md](docs/LANGCHAIN_POLICY_RAG_COMPARISON.md)。

发票图片案例故事线增强已完成，后续等待总控验收后再决定细节优化或投递材料收口。

Phase 3B 环境检查入口：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\verify_lora_notebook_env.py
.\.venv\Scripts\python.exe scripts\phase3\bootstrap_lora_notebook.py
.\.venv\Scripts\python.exe scripts\phase3\base_inference_smoke.py
```

## Phase 1 状态

Phase 1 已完成数据处理、OCR baseline、LayoutLMv3 微调、字段级 F1、日期错误分析
和 checkpoint inference 证据封板。模型抽取仍保持离线，尚未替换 API 占位字段。
