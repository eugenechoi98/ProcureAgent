# 日期版式挑战与日期重建

- 图片、OCR 和 LayoutLMv3 bbox 预测通过同一个 `sample_id` 关联。
- LayoutLMv3 为本地 checkpoint 的 CPU 离线真实推理。
- SROIE Task 3 只提供 company/address/date/total；采购单号和收货单号是明确标注的 mock 上下文。
- Phase 2 结果由现有 AgentInvoiceProcessor 实时计算后固化。
- 单案例只说明链路和具体输出，不代表数据集整体 F1。
