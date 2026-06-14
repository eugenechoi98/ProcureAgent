# CONTEXT.md

## 当前目标
完成公网 Demo 网页展示最终收口，并将已验证 Space 包合并到 main。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`，展示收口远端 commit 为 `c1a6bcc`。
- 三页签结构不变；发票审核页新增操作引导和 5 个中文案例摘要。
- 模型实验页前移 LoRA Guard 亮点，完整指标、长表和 JSON 默认折叠。
- 系统架构页强化“受控采购审核 Agent”定位并统一链路术语。
- 本地桌面与 390px 页面检查通过；公开 HTTP、config 和 Guard 回退 API 通过。
- 案例图片不是 SROIE 样本，不运行单图 LayoutLMv3，也不用于证明数据集级 F1。

## 下一步
完成文档提交、合并 main 并 push origin/main，随后等待总控验收。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- Guard / fallback 仅使用现有本地 fake provider 展示治理路径，模板仍是正式输出。
- 不新增第 4 页签，不修改 Phase 1、Phase 2 风险规则或 Phase 3H 语义。

## 最后更新时间
2026-06-14
