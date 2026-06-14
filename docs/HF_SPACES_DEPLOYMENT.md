# Hugging Face Spaces Deployment

## Public URLs

- Hub: https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App: https://eugene-98-procureguard-ai-demo.hf.space
- Visibility: Public
- Runtime: `RUNNING` on `cpu-basic`
- 当前远端 commit：`c1a6bccec34f2fca53a5890372854dc0ee9d2179`

Batch C.1 本地发布包、Batch C.2 网页端 Space 创建和 Batch C.3 受控上传均已完成。远端 commit 为 `d1d12ae4529b47c34b6b4bd50cd27d0303cfa6c2`。

## Public Scope

公网 Demo 已完成中文化，包含：

1. 发票审核：中文操作引导、5 个案例摘要、六区块故事线和默认折叠技术输出
2. 模型实验：三项核心指标与 LoRA Guard 亮点前置，完整指标、长表和原始 JSON 默认折叠
3. 系统架构：统一中文链路术语，突出受控采购审核 Agent 定位

公开页面不加载 LayoutLMv3、Qwen 或真实 LoRA，不包含模型权重、checkpoint、adapter、Notebook、本地数据库或训练脚本，不需要 GPU、API Key、secrets 或外部模型 API。

## Verification

- Hub、App 和 `/config` 返回 HTTP 200，无需登录。
- 三个页签、默认 `normal_invoice + template`、Model Lab 指标和 Architecture 链路已从公开 Gradio config 核验。
- 公开 `run_audit` API 返回 risk level、recommended action、facts hash 和完整 AuditReport。
- 案例增强版本的公开 `/config` 已确认六个案例区块，默认 `run_audit` API 返回低风险和自动通过。
- 展示收口版本的公开 `/config` 已确认案例摘要、模型实验阅读引导和两组默认折叠长表。
- 公开 `vendor_name_mismatch + experimental_guard_fail` API 已确认 Guard 拒绝并回退确定性模板。
- 本地桌面与 390px 窄屏视觉检查通过，未发现布局重叠或前端错误。
- 公开 Gradio config 已确认三个中文页签、中文使用说明和中文架构链路。
- 用户已完成人工浏览器验收：公网页面、中文化页面、发票审核、模型实验和系统架构均为 PASS，未发现前端错误。
- 未单独记录桌面与移动设备专项视觉结果。

当前准确状态：

```text
hf_space_created=true
hf_space_uploaded=true
manual_browser_check_required=false
online_deployment_verified=true
layoutlmv3_live_inference=false
real_lora_live_inference=false
model_weights_included=false
gpu_required=false
api_key_required=false
secrets_required=false
production_ready=false
```

公网 Unified Portfolio Demo 已部署，不等于在线 LayoutLMv3、真实 LoRA 在线推理、生产可用、生产指标或 official test。

模型实验页新增真实离线 `GRN-20260149` 案例，展示 LoRA 原始输出、Guard 拒绝原因和确定性模板回退。发票审核页图片全部是合成示意图，不是 SROIE 样本或单图 checkpoint 输出，不启用真实 LoRA 在线推理，也不改变审核结论。

## Local Package Checks

```powershell
.\.venv\Scripts\python.exe scripts\demo\build_hf_space_package.py
.\.venv\Scripts\python.exe scripts\demo\run_hf_space_package_smoke.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py --include-online-check
```

默认 readiness 不访问公网；只有 `--include-online-check` 才检查公开 URL。
