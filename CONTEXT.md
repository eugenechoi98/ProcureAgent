# CONTEXT.md

## 当前目标
完成 Phase 1 OCR Baseline 与 SROIE 最小可运行闭环。

## 当前进度
- Phase 2 已封板，基线 commit 为 `c40bb14`。
- Phase 1 模型抽取骨架已完成。
- OCR token 契约、PaddleOCR 适配器、OCR + Regex baseline、SROIE reader、字段级 F1 和错误分析已完成。
- fixture smoke 流程已通过。

## 下一步
在真实 SROIE 数据集上运行 OCR baseline，记录真实字段级 F1，并完善 LayoutLMv3 数据预处理和训练 Notebook。

## 注意事项
- fixture 结果只用于 smoke test，不能写入简历。
- Phase 1 不修改后端共享契约。
- PaddleOCR 是可选依赖，不进入默认后端运行环境。

## 最后更新时间
2026-06-10
