# Phase 4A Productization Gap Audit Report

## 结果

Phase 4A：PASS。

项目已达到 public portfolio demo 和核心规则链工程验证水平，但未达到真实用户 MVP、干净 clone 开源运行或生产商用水平。

## Top 5

1. 干净 clone Quickstart、`.env.example`、sample、LICENSE、隐私与数据归属。
2. 手动发票字段 + mock PO/GRN 的真实用户输入流。
3. 安全免责声明、字段来源和 failure/fallback 状态统一。
4. AuditReport JSON/Markdown 导出与人工审核 UX。
5. API 错误码、初始化/migration、demo seed/reset 和 OpenAPI 示例。

## 路线判断

- Phase 4B 阻塞开源发布，应立即开始。
- Phase 4C 阻塞真实用户完成首次审核，应在 4B 后开始。
- Phase 4D 补齐报告带走和人工复核闭环。
- Phase 4E、4F 可选，不阻塞手动输入 MVP。
- 在线 LoRA 不进入路线；3J/3K 保持离线治理证据。

## 关键边界

- HF Space 是作品集 Demo，不是生产系统。
- 公网 Demo 不支持任意发票在线 LayoutLMv3 推理。
- A/B 的 PO/GRN 是 mock；C 的输入事实是 synthetic fixture。
- `risk_level` 和 `recommended_action` 只能由确定性规则生成。
- deterministic template 仍是正式默认解释路径。

## 验证

- 指定输入文档存在性：通过。
- Phase 4 JSON parse：通过后落档。
- Markdown 本地链接检查：通过后落档。
- 全量测试：未运行；本轮无业务代码变更，且工作区包含其他线程未提交改动。
