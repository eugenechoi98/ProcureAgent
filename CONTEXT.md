# CONTEXT.md

## 当前目标
完成 Batch H0 端到端真实证据资产生成，不修改公网 Demo 页面。

## 当前进度
- 找到 SROIE validation 原图、OCR bbox、完整 LayoutLMv3 checkpoint 和既有 prediction artifact。
- case A/B 已生成同 sample_id 的原图、OCR 可视化、CPU 离线真实 checkpoint prediction、结构化字段和 Phase 2 运行结果。
- Phase 2 使用真实现有引擎；PO/GRN/invoice number 是明确标注的 mock 采购上下文，不冒充图片抽取字段。
- case C 使用首轮真实离线 LoRA 输出，当前 Guard 实际拒绝 `GRN-20260149`，并回退确定性模板。
- 证据包包含 manifest、claim 边界和 SHA-256；未修改或上传 Hugging Face Space。

## 下一步
完成验证、提交、合并 main，等待用户确认后再进入 Batch H1。

## 注意事项
- 单案例不能证明整体 F1，整体指标仍只属于 Model Lab。
- SROIE 图片按 CC BY 4.0 数据卡口径归属，仍需保留企业联系信息的隐私复核提示。
- 不修改 Phase 1、Phase 2 风险规则或 Phase 3H Guard/fallback 语义。

## 最后更新时间
2026-06-14
