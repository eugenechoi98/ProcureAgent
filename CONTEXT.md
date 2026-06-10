# CONTEXT.md

## 当前目标
完成 Phase 1 模型抽取能力。

## 当前进度
- Phase 2 已封板。
- Phase 1A 已完成：OCR token、PaddleOCR 适配器、OCR + Regex baseline、SROIE reader、fixture F1 和错误分析。
- Phase 1B 已完成：BIO 标签、token alignment、LayoutLMv3 Dataset、DataLoader 和训练 Notebook 代码。
- Phase 1C 已完成 ModelScope 镜像适配：626 train、361 test 的图片和 OCR annotation 已整理。
- 真实 OCR + Regex baseline 已对 987 个样本完成预测。
- ModelScope 镜像缺少 `company/address/date/total` entity ground truth，因此真实字段级 F1 未运行。
- fixture 和真实数据 LayoutLMv3 batch smoke 已通过，fixture 单 batch forward 已通过。

## 下一步
补充官方 SROIE Task 3 entity ground truth 到 `raw/train/key` 和 `raw/test/key`。随后重新生成带标签 processed JSONL，运行真实字段级 F1，并在具备合适 GPU 的环境中执行 LayoutLMv3 fine-tuning。

## 注意事项
- fixture 分数不能作为简历指标。
- 不提交真实数据集、模型权重或缓存。
- Phase 1 不修改后端共享契约。
- 当前模型尚未接入 API。
- baseline prediction coverage 不是准确率，不能作为模型效果。

## 最后更新时间
2026-06-10
