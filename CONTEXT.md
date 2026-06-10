# CONTEXT.md

## 当前目标
在 GPU Notebook 中运行 LayoutLMv3 完整 fine-tuning。

## 当前进度
- Phase 2 已封板。
- Phase 1A-D 已完成：OCR baseline、Task 3 数据、BIO alignment、Dataset、DataLoader、单 batch forward 和 PaddleOCR smoke。
- GPU 训练 Notebook 与运行手册已准备完成。
- 当前尚未运行完整 fine-tuning。

## 下一步
用户在 ModelScope GPU Notebook 或 Colab 中运行训练 Notebook，记录 loss 曲线、fine-tuned validation 字段级 F1、错误案例和最佳 checkpoint。

## 注意事项
- 当前 baseline macro F1 为 0.4387。
- validation 使用 local_validation_split_seed_42，不是 official test。
- checkpoint、模型权重和真实数据不提交 Git。
- 模型训练完成后再决定是否接入 API。

## 最后更新时间
2026-06-10
