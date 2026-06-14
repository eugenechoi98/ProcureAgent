# E2E Case Evidence Report

## 审计结论

- 找到真实可追溯图片：YES（SROIE validation 样本）。
- 图片与 LayoutLMv3 prediction 一一对应：YES（同一 sample_id）。
- OCR / prediction bbox 可视化：YES。
- extracted fields 进入 Phase 2 实时审核：YES，但 PO/GRN 为明确标注的 mock 上下文。
- LoRA Guard/fallback 真实案例：YES，原始输出来自首轮真实离线评测。

## 可进入后续 Demo 的案例

- `case_a_standard_pass`：标准收据字段抽取与低风险审核；LayoutLMv3=real_checkpoint_inference；Phase2=real_runtime_engine；LoRA=not_available。
- `case_b_date_layout_challenge`：日期版式挑战与日期重建；LayoutLMv3=real_checkpoint_inference；Phase2=real_runtime_engine；LoRA=not_available。
- `case_c_lora_guard_fallback`：真实离线 LoRA 幻觉、Guard 拦截与模板回退；LayoutLMv3=not_available；Phase2=fixture_only；LoRA=real_offline_model_output。

## 关键边界

- A/B 的图片、OCR 和模型预测可以按 sample_id 追溯。
- A/B 的采购单号和收货单号不是图片抽取字段，而是 Phase 2 mock 上下文。
- C 的输入事实是 synthetic evaluation fixture，只有 LoRA 原始输出和 Guard 校验属于真实离线证据。
- 单案例不能用于证明整体 F1；整体指标仍只属于 Model Lab。
- 本轮未修改或上传 Hugging Face Space。

## 许可证与隐私

- 数据源：Voxel51/scanned_receipts，源自 ICDAR 2019 SROIE。
- 数据卡许可证：CC BY 4.0；公开展示时必须保留归属。
- 所选图片包含企业地址、电话或订单信息；未观察到自然人顾客姓名，发布前仍建议再次人工复核。
