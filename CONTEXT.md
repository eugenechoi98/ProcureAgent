# CONTEXT.md

## 当前目标
Batch C.3 已完成受控上传与机器化公网 smoke，等待人工视觉验收和总控确认。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`，HTTP、Gradio config 和 `run_audit` API 已通过。
- Invoice Audit、Model Lab、Architecture 三页签已公开；Model Lab 仍只展示真实离线 artifacts。
- 自动化可视化浏览器加载超时，因此 `manual_browser_check_required=true`，暂不声明完整在线部署验收完成。

## 下一步
用户仅需打开公网 App 完成一次人工视觉检查；通过后再更新 `online_deployment_verified`。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- 公网 Unified Portfolio Demo 不等于在线模型推理，也不代表生产可用或 official test。
- Docker runtime 仍未在当前本机环境验证。

## 最后更新时间
2026-06-13
