# CONTEXT.md

## 当前目标
Batch B：Unified Gradio Demo 已完成本地初版，等待集中总控验收。

## 当前进度
- Phase 1 已封板：corrected pure LayoutLMv3 macro F1=0.8067。
- Phase 2 已封板：FastAPI、SQLite、5 个 Agent 工具、Policy RAG、Risk Engine 和 Audit Trace 已完成。
- Phase 3 已完成两轮真实 QLoRA 训练与评测；第二轮未通过 hard gate，第三次训练暂停。
- Phase 3H 已封板：Canonical Facts、Template、Guard、Fallback、Audit Trail 和 additive API explanation 已完成。
- Local Gradio Demo Baseline 已完成并合并到 `main`，Gradio 使用独立 `demo` optional dependency。
- 统一 Portfolio Demo 已在本地完成 Invoice Audit、Model Lab、Architecture 三个页签。
- Model Lab 只读取 `demo/model_lab/` 真实离线轻量 artifacts。

## 下一步
由审查与总控对话验收 Batch B；通过后再进入 Batch C：Hugging Face Spaces 可部署性与发布准备。

## 注意事项
- 不继续扩张 Phase 3H，不修改 Phase 2 风险规则、Agent、共享 schema 或数据库。
- 不立即部署 Hugging Face Spaces；先完成 Model Lab artifacts packaging 和统一 Demo。
- 默认实时路径继续使用 Phase 2、Policy RAG、Risk Engine、Canonical Facts、Template、Guard/Fallback 和 AuditReport。
- LayoutLMv3 与 LoRA 默认展示真实离线实验结果，不表述为网页实时推理。
- Model Lab package 不包含模型权重、adapter、checkpoint、公开图片副本或实时 inference。
- 当前没有网页实时 LayoutLMv3，没有网页实时真实 LoRA，没有部署 Hugging Face Space。
- 在线 LayoutLMv3、在线真实 LoRA、GPU Space 和 Phase 3I 仅为后续 optional feasibility。
- LangChain、Docker Compose、GitHub Actions CI 和最终 README/GIF/Resume 按冻结批次依次收口。

## 最后更新时间
2026-06-13
