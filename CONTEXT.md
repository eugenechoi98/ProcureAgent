# CONTEXT.md

## 当前目标
Phase 2 已完成，准备进入下一阶段。

## 当前进度
- 共享契约层已完成并冻结。
- FastAPI 后端基础已完成。
- Agent 与规则闭环已完成。
- `POST /invoices/upload` 默认进入真实规则链。
- 显式 `processing_mode=mock` 保留用于后端 smoke test。
- 真实链已写入 ExtractedFields、ValidationResult、AuditReport 和 Audit Trace。
- 全量测试已通过。

## 下一步
回到审查与总控对话确认下一阶段。优先新开 Phase 1 模型抽取开发对话，搭建 LayoutLMv3、PaddleOCR、SROIE/CORD 数据预处理、OCR baseline、训练 Notebook 和字段级 F1 评测。

## 注意事项
- 共享契约保持冻结。
- mock_processor 保留，不删除。
- Phase 1 如果需要调整模型输出字段，必须先回到审查与总控对话确认。
- 当前真实链中的字段抽取仍为 mock，后续由 Phase 1 模型抽取模块替换。

## 最后更新时间
2026-06-10
