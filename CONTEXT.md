# CONTEXT.md

## 当前目标
完成 Phase 1 带实体标签的数据准备与有效 LayoutLMv3 训练前验证。

## 当前进度
- Phase 2 已封板。
- Phase 1A 已完成 OCR baseline fixture 闭环。
- Phase 1B 已完成 LayoutLMv3 数据管线和训练 Notebook。
- Phase 1C 已完成 ModelScope 镜像适配、真实图片预测和单 batch smoke。
- Phase 1D 已接入带 company/address/date/total 实体标签的 Voxel51/scanned_receipts。
- 真实 validation baseline、BIO alignment 和有效单 batch forward 已完成。
- PaddleOCR 3.6.0 + PaddlePaddle 3.3.1 端到端 smoke 已完成。

## 下一步
在 Colab 或 ModelScope GPU Notebook 中运行 LayoutLMv3 完整 fine-tuning，记录 loss 曲线、真实 validation 字段级 F1 和错误案例。

## 注意事项
- 默认后端依赖与 extraction 重型依赖保持隔离。
- validation 是固定 seed 本地拆分，不是官方 test。
- 不提交真实数据集、模型权重或缓存。
- Phase 1 不修改后端共享契约。
- 当前模型尚未接入 API。
- fixture 分数不能作为简历指标。

## 最后更新时间
2026-06-10
