# CONTEXT.md

## 当前目标
完成 Phase 1 模型抽取能力。

## 当前进度
- Phase 2 已封板。
- Phase 1A 已完成：OCR token、PaddleOCR 适配器、OCR + Regex baseline、SROIE reader、fixture F1 和错误分析。
- Phase 1B 已完成：BIO 标签、token alignment、LayoutLMv3 Dataset、DataLoader 和训练 Notebook 代码。
- 真实 SROIE baseline 是否已运行，以本机数据是否存在为准。

## 下一步
如果真实 SROIE 数据尚未放置，先完成人工下载并运行真实 baseline。随后在 Colab 或具备合适 GPU 的环境中运行 LayoutLMv3 fine-tuning，记录真实字段级 F1、loss 曲线和错误案例。

## 注意事项
- fixture 分数不能作为简历指标。
- 不提交真实数据集、模型权重或缓存。
- Phase 1 不修改后端共享契约。
- 当前模型尚未接入 API。

## 最后更新时间
2026-06-10
