# LayoutLMv3 Extraction Lab

本目录展示 Phase 1 已完成的真实离线结果。

固定口径：

- `evaluation_split=local_validation_split_seed_42`
- `official_test=false`
- `inference_scope=offline_checkpoint_inference`
- `integrated_into_api=false`

核心数字：

- OCR + Regex baseline macro F1: `0.4387`
- 首轮 LayoutLMv3 macro F1: `0.6231`
- 日期清洗后 corrected LayoutLMv3 macro F1: `0.8067`
- Date F1: `0.1423 -> 0.8764`

这些文件只服务后续 Model Lab 展示，不代表线上实时抽取能力。
