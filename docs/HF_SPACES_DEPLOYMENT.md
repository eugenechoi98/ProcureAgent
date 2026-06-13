# Hugging Face Spaces Deployment

## Public URLs

- Hub: https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App: https://eugene-98-procureguard-ai-demo.hf.space
- Visibility: Public
- Runtime: `RUNNING` on `cpu-basic`

Batch C.1 本地发布包、Batch C.2 网页端 Space 创建和 Batch C.3 受控上传均已完成。远端 commit 为 `d1d12ae4529b47c34b6b4bd50cd27d0303cfa6c2`。

## Public Scope

公网 Demo 包含：

1. Invoice Audit
2. Model Lab 离线 artifacts
3. Architecture

公开页面不加载 LayoutLMv3、Qwen 或真实 LoRA，不包含模型权重、checkpoint、adapter、Notebook、本地数据库或训练脚本，不需要 GPU、API Key、secrets 或外部模型 API。

## Verification

- Hub、App 和 `/config` 返回 HTTP 200，无需登录。
- 三个页签、默认 `normal_invoice + template`、Model Lab 指标和 Architecture 链路已从公开 Gradio config 核验。
- 公开 `run_audit` API 返回 risk level、recommended action、facts hash 和完整 AuditReport。
- 自动化视觉浏览器加载在当前环境超时，因此仍需人工打开 App 做一次视觉检查。

当前准确状态：

```text
hf_space_created=true
hf_space_uploaded=true
manual_browser_check_required=true
online_deployment_verified=false
layoutlmv3_live_inference=false
real_lora_live_inference=false
```

公网 Unified Portfolio Demo 已部署，不等于在线 LayoutLMv3、真实 LoRA 在线推理、生产可用、生产指标或 official test。

## Local Package Checks

```powershell
.\.venv\Scripts\python.exe scripts\demo\build_hf_space_package.py
.\.venv\Scripts\python.exe scripts\demo\run_hf_space_package_smoke.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py --include-online-check
```

默认 readiness 不访问公网；只有 `--include-online-check` 才检查公开 URL。
