# Hugging Face Spaces Deployment

## Public URLs

- Hub: https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- App: https://eugene-98-procureguard-ai-demo.hf.space
- Visibility: Public
- Runtime: `RUNNING` on `cpu-basic`
- 当前远端 commit：`1235f47642277cb9c03c45f2ea44f8632d990710`

Batch C.1 本地发布包、Batch C.2 网页端 Space 创建和 Batch C.3 受控上传均已完成。远端 commit 为 `d1d12ae4529b47c34b6b4bd50cd27d0303cfa6c2`。

## Public Scope

公网 Demo 已完成中文化，包含：

1. 发票审核：3 个 H0 端到端证据链案例为主视图，5 个合成流程案例保留在默认收起的补充区
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
- H1 远端 config 已确认默认案例 A、三案例选择器、三张证据图、默认折叠技术明细和默认折叠合成案例区。
- A/B 的 SROIE 图片保留 CC BY 4.0 归属；人工复核未发现可识别自然人客户姓名，本次不做遮罩。

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

发票审核页 A/B 展示 SROIE 图片、OCR、真实离线 checkpoint 预测和已提交 Phase 2 结果，PO/GRN 明确为 mock 上下文；案例 C 展示真实离线 LoRA artifact、Guard 拒绝和确定性模板回退。单案例不作为整体 F1 证明，也不启用在线模型推理。

## Local Package Checks

```powershell
.\.venv\Scripts\python.exe scripts\demo\build_hf_space_package.py
.\.venv\Scripts\python.exe scripts\demo\run_hf_space_package_smoke.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py
.\.venv\Scripts\python.exe scripts\release\verify_portfolio_release_readiness.py --include-online-check
```

默认 readiness 不访问公网；只有 `--include-online-check` 才检查公开 URL。
