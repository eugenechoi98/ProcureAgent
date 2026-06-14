# CONTEXT.md

## 当前目标
完成公网 Demo 发票案例交互修复，并通过浏览器验证运行前后状态。

## 当前进度
- Public Space：https://huggingface.co/spaces/eugene-98/procureguard-ai-demo
- Public App：https://eugene-98-procureguard-ai-demo.hf.space
- Space 运行于 `cpu-basic`；本轮将更新交互修复后的远端 commit。
- 三页签和 5 个案例保持不变；解释模式使用中文标签但内部值不变。
- 案例切换后，三单匹配、审核证据、最终风险和正式解释显示“尚未运行”。
- 点击“运行审核”会执行既有 `DemoService` 审核链，并在按钮下方显示完成摘要，同时生成各结果区内容。
- 本地 Space 包已通过浏览器逐案例运行验证；技术 JSON 继续默认折叠。
- 案例图片不是 SROIE 样本，不运行单图 LayoutLMv3，也不用于证明数据集级 F1。

## 下一步
完成全量测试、公网上传与浏览器复验，合并 main 并 push origin/main。

## 注意事项
- 不加载 LayoutLMv3、Qwen 或真实 LoRA，不使用 GPU、API Key、secrets 或外部模型 API。
- Guard / fallback 仅使用现有本地 fake provider 展示治理路径，模板仍是正式输出。
- 不新增第 4 页签，不修改 Phase 1、Phase 2 风险规则或 Phase 3H 语义。

## 最后更新时间
2026-06-14
