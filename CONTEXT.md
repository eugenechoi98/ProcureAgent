# CONTEXT.md

## 当前目标
完成 Batch H1，将 H0 端到端真实证据链接入 Hugging Face Demo。

## 当前进度
- 发票审核页主视图已接入案例 A/B/C，默认展示 H0 已验收证据包。
- A/B 展示同 sample_id 的 SROIE 原图、OCR、离线 LayoutLMv3 预测与 Phase 2 结果；PO/GRN 明确标注为 mock 上下文。
- C 展示真实离线 LoRA 输出、Guard `REJECT` 和确定性模板 fallback，不伪造图片或在线推理。
- 原 5 个合成流程案例保留在默认收起的补充区，三页签结构不变。
- Space 发布包已纳入轻量证据文件，不包含模型权重。

## 下一步
完成测试、浏览器验收、Space 上传、Git 合并与推送。

## 注意事项
- 单案例不能证明整体 F1，整体指标仍只属于 Model Lab。
- SROIE 图片按 CC BY 4.0 数据卡口径归属；人工复核未发现可识别自然人客户姓名，本次不遮罩并保留归属说明。
- 不修改 Phase 1、Phase 2 风险规则或 Phase 3H Guard/fallback 语义。

## 最后更新时间
2026-06-14
