# CONTEXT.md

## 当前目标
Batch A：Model Lab Artifacts Packaging 已完成初版，等待审查与后续 Unified Gradio Demo 接入。

## 当前进度
- Phase 1 已封板：corrected pure LayoutLMv3 macro F1=0.8067。
- Phase 2 已封板：FastAPI、SQLite、5 个 Agent 工具、Policy RAG、Risk Engine 和 Audit Trace 已完成。
- Phase 3 已完成两轮真实 QLoRA 训练与评测；第二轮未通过 hard gate，第三次训练暂停。
- Phase 3H 已封板：Canonical Facts、Template、Guard、Fallback、Audit Trail 和 additive API explanation 已完成。
- Local Gradio Demo Baseline 已完成并合并到 `main`，Gradio 使用独立 `demo` optional dependency。
- 统一 Portfolio Demo 冻结为 Invoice Audit、Model Lab、Architecture 三个页签；Tab 1 基线完成，Model Lab 轻量 artifacts 已整理到 `demo/model_lab/`。

## 下一步
由审查与总控对话验收 Batch A artifacts；通过后进入 Batch B：Unified Gradio Demo 接入 Model Lab 页签。

## 注意事项
- 不继续扩张 Phase 3H，不修改 Phase 2 风险规则、Agent、共享 schema 或数据库。
- 不立即部署 Hugging Face Spaces；先完成 Model Lab artifacts packaging 和统一 Demo。
- 默认实时路径继续使用 Phase 2、Policy RAG、Risk Engine、Canonical Facts、Template、Guard/Fallback 和 AuditReport。
- LayoutLMv3 与 LoRA 默认展示真实离线实验结果，不表述为网页实时推理。
- Model Lab package 不包含模型权重、adapter、checkpoint、公开图片副本或实时 inference。
- 在线 LayoutLMv3、在线真实 LoRA、GPU Space 和 Phase 3I 仅为后续 optional feasibility。
- LangChain、Docker Compose、GitHub Actions CI 和最终 README/GIF/Resume 按冻结批次依次收口。

## 最后更新时间
2026-06-13
