# CONTEXT.md

## 当前目标
完成发票审核页图片案例故事线增强，并将已验证 Space 包合并到 main。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`，案例增强远端 commit 为 `9691cf2`。
- 三页签结构不变；发票审核页新增 5 个合成图片案例和六区块故事线。
- 本地桌面与 390px 页面检查通过；公开 HTTP、config 和 `run_audit` API 通过。
- 案例图片不是 SROIE 样本，不运行单图 LayoutLMv3，也不用于证明数据集级 F1。

## 下一步
完成全量测试、合并 main 并 push origin/main，随后等待总控验收。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- Guard / fallback 仅使用现有本地 fake provider 展示治理路径，模板仍是正式输出。
- 不新增第 4 页签，不修改 Phase 1、Phase 2 风险规则或 Phase 3H 语义。

## 最后更新时间
2026-06-14
