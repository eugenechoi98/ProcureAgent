# CONTEXT.md

## 当前目标
完成 Portfolio Final Polish：README 第一屏、Demo Walkthrough、LoRA Guard 可视化证据和双语简历描述。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`，Portfolio Final Polish 远端 commit 为 `80a5e03`。
- 发票审核、模型实验、系统架构三个中文页签已公开，使用说明和业务标签已中文化。
- 模型实验页已突出三项核心指标，移除独立缺失区域，并将原始 JSON 收进默认折叠区。
- HTTP、Gradio config 和 `run_audit` API 已通过；公网页面、中文化页面及三个核心页签均已通过用户人工验收。
- 当前状态为 `manual_browser_check_required=false`、`online_deployment_verified=true`。
- Model Lab 已增加真实离线 `GRN-20260149` 的 LoRA 输出、Guard 拒绝与模板回退展示。
- README、Demo Walkthrough 和双语简历描述已按“受控采购发票审核 Agent”定位收口。

## 下一步
完成全量验证和 Git 合并；截图/GIF 因当前浏览器进程无法持久化二进制到工作区而不纳入本轮提交。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- 公网 Unified Portfolio Demo 不等于在线模型推理，也不代表生产可用或 official test。
- Docker runtime 仍未在当前本机环境验证。

## 最后更新时间
2026-06-14
