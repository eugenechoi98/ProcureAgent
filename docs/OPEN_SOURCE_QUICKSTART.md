# Open-source Quickstart

本指南用于从 clean clone 在 Windows PowerShell 中完成 CPU-only 最小验证。它不会下载模型、运行 GPU Notebook、执行在线 LayoutLMv3 或加载真实 LoRA。

## 前置条件

- Git
- Python 3.10 或 3.11，推荐 3.11
- PowerShell

## 1. 创建环境

```powershell
git clone <your-repository-url>
cd ProcureAgent
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[demo,test]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip check
```

`.env` 只记录本地路径示例。当前应用不会自动加载 dotenv 文件；PowerShell 用户如需覆盖默认路径，应显式设置：

```powershell
$env:DATABASE_PATH="data/procureguard.db"
$env:UPLOAD_DIR="uploads"
```

FastAPI 首次启动时会自动创建 SQLite schema，并写入 synthetic/mock PO、GRN 和政策数据。

## 2. 最小 AuditReport smoke

```powershell
.\.venv\Scripts\python.exe scripts\samples\run_sample_audit.py
```

该命令读取 `samples/invoices/clean_invoice.json`，使用内存 SQLite 和现有 mock procurement context，运行 Phase 2 确定性审核主链并打印 AuditReport JSON。它不读取图片、不运行 OCR/LayoutLMv3、不访问网络，也不写本地数据库。

预期关键结果：

```text
risk_level = low
recommended_action = auto_approve
explanation_source = template
```

## 3. 启动 FastAPI

```powershell
.\.venv\Scripts\python.exe -m uvicorn procureguard.api.main:app --host 127.0.0.1 --port 8000
```

打开：

- Health: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

当前 `/invoices/upload` 会保存上传文件，但不会在线运行 LayoutLMv3。请只使用非敏感测试文件，并阅读 [隐私与数据边界](PRIVACY_AND_DATA_BOUNDARIES.md)。

### Manual Audit MVP

```powershell
$body = Get-Content -Raw -Encoding UTF8 samples\manual_audit\request_standard_pass.json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/mvp/manual-audit `
  -ContentType "application/json" `
  -Body $body
```

该入口只接收手动字段和显式 mock PO/GRN，使用请求级内存数据库，不写默认 SQLite。完整说明见 [Phase 4C](phase4c_user_facing_mvp_input_flow.md)。

审核完成后可在同一 API 进程中查看待复核队列、提交决定并导出：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/mvp/manual-audit/review-queue
Invoke-WebRequest "http://127.0.0.1:8000/api/mvp/manual-audit/<audit_id>/export?format=markdown"
```

完整 review/export 示例见 [Phase 4D](phase4d_audit_report_export_review_ux.md)。进程重启后 Manual Audit store 会清空。

## 4. 启动本地 Demo

```powershell
$env:NO_PROXY="127.0.0.1,localhost"
$env:no_proxy="127.0.0.1,localhost"
$env:GRADIO_ANALYTICS_ENABLED="False"
.\.venv\Scripts\python.exe -m demo.app
```

打开 `http://127.0.0.1:7860`。该页面是作品集 Demo，展示预生成字段、离线模型证据、mock context 和确定性审核链，不是生产系统。

## 5. 分层测试

```powershell
# smoke：无 GPU、无模型下载、无网络
.\.venv\Scripts\python.exe scripts\samples\run_sample_audit.py
.\.venv\Scripts\python.exe scripts\phase4\run_manual_audit_sample.py --case all
.\.venv\Scripts\python.exe scripts\demo\verify_demo_readiness.py
.\.venv\Scripts\python.exe -m pytest tests\test_api.py -q

# phase1：代码、fixture 和已提交轻量报告验证；不运行 GPU Notebook/live inference
.\.venv\Scripts\python.exe -m pytest tests\test_phase1_extraction.py tests\test_phase1_results.py tests\test_validation_inference.py -q

# phase2：共享契约、API、规则链和人工审核
.\.venv\Scripts\python.exe -m pytest tests\test_shared_contracts.py tests\test_api.py tests\test_agent_rules.py -q

# phase3：数据、评测、Guard/Fallback、Structured Output 和 Citation 离线验证
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_dataset.py tests\test_phase3_evaluation.py tests\test_phase3h_guarded_explanation.py tests\test_phase3h_integration.py tests\test_phase3j_structured_output.py tests\test_phase3k_evidence_citation.py -q

# full：默认 CPU-only；不下载模型，不运行 GPU Notebook 或 live inference
.\.venv\Scripts\python.exe -m pytest tests -q
```

Phase 1/3 的部分测试会读取仓库内已提交的轻量 fixture、Markdown/JSON 报告或 Model Lab 包；被 `.gitignore` 排除的本地 checkpoint、adapter 和训练目录不属于默认 full test 前置条件。

## Optional Phase 4F extraction spike

该路径不是 clean-clone Quickstart 的必需步骤。先执行只读检查：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[extraction,test]"
.\.venv\Scripts\python.exe scripts\phase4\check_live_extraction_assets.py
```

仓库不包含微调 checkpoint，缺资产时脚本返回可解析 JSON 和非零 exit code，不会下载模型。恢复完整 checkpoint、processor 和 BIO label map 后，按 [Phase 4F 说明](phase4f_local_live_extraction_spike.md) 使用公开或 synthetic 图片运行；该脚本不进入 Phase 2，也不生成风险或动作。

## 7. Release hygiene

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
git status --short
git diff --check
```

发布前还应检查 Markdown 链接、JSON 可解析性，以及 `git ls-files` 中没有数据库、uploads、模型权重、checkpoint、adapter、缓存、原始训练 artifacts 或大型数据压缩包。
