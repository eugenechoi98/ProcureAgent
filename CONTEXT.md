# CONTEXT.md

## 当前目标
Batch C.4 公网 Demo 模型实验页展示优化已完成，等待用户人工视觉复验。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`，展示优化版本远端 commit 为 `5f541c9`。
- 发票审核、模型实验、系统架构三个中文页签已公开，使用说明和业务标签已中文化。
- 模型实验页已突出三项核心指标，移除独立缺失区域，并将原始 JSON 收进默认折叠区。
- HTTP、Gradio config 和 `run_audit` API 已通过；自动化浏览器切换模型实验页时超时，因此 `manual_browser_check_required=true`。

## 下一步
用户仅需打开公网 App 完成一次人工视觉检查；通过后再更新 `online_deployment_verified`。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- 公网 Unified Portfolio Demo 不等于在线模型推理，也不代表生产可用或 official test。
- Docker runtime 仍未在当前本机环境验证。

## 最后更新时间
2026-06-14
