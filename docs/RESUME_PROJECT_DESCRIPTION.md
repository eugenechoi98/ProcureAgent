# Resume Project Description

## 中文

### ProcureGuard AI｜受控采购发票审核 Agent

- 使用 PyTorch + Transformers 完成 LayoutLMv3 发票字段抽取实验，对比 OCR + Regex baseline，Macro F1 从 0.4387 提升至 0.8067，Date F1 从 0.1423 提升至 0.8764，并完成字段级错误分析。
- 构建采购发票审核工作流，集成三单匹配、重复发票检测、政策 RAG 和确定性风险规则，输出风险等级、建议动作、证据链与结构化审核报告。
- 完成 Qwen2.5-0.5B QLoRA 异常解释实验，并基于 hallucination 评测结果设计 Guard / Fallback 受控解释层，防止生成模型篡改风险等级、建议动作和异常类型。
- 构建 CPU-only Hugging Face 作品集 Demo，以 SROIE 图片、LayoutLMv3 离线 checkpoint prediction、Phase 2 审核和真实 LoRA Guard/fallback artifact 展示可追溯证据链，并明确区分模型字段与 mock PO/GRN 上下文。

## English

### ProcureGuard AI | Controlled Procurement Invoice Review Agent

- Built a LayoutLMv3 invoice field extraction experiment with PyTorch and Transformers, improving macro F1 from a 0.4387 OCR + Regex baseline to 0.8067 and date F1 from 0.1423 to 0.8764, with field-level error analysis.
- Developed a procurement invoice review workflow integrating three-way matching, duplicate invoice detection, policy RAG, and deterministic risk rules to produce risk levels, recommended actions, evidence trails, and structured audit reports.
- Completed two Qwen2.5-0.5B QLoRA explanation experiments and designed a Guard / Fallback layer from hallucination evaluation findings so generated text cannot alter risk levels, recommended actions, or anomaly types.
- Shipped a CPU-only Hugging Face portfolio Demo connecting SROIE images, offline LayoutLMv3 checkpoint predictions, Phase 2 audits, and real LoRA Guard/fallback artifacts while explicitly separating model fields from mock PO/GRN context.

## Accuracy Notes

- LayoutLMv3 metrics use `local_validation_split_seed_42` and are not official-test results.
- LoRA is not the default production explanation path; it remains a shadow, experimental, and Phase 3I evaluation candidate.
- The public Demo is CPU-only and is not presented as a production-ready financial system.
- The public Demo does not support arbitrary invoice upload or online LayoutLMv3/LoRA inference.
