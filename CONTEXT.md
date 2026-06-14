# CONTEXT.md

## 当前目标
Phase 3I LoRA 后续路线评估。

## 当前进度
- H0/H1/H2 Demo 基线已完成。
- Phase 3I 已完成两轮失败根因、五条候选路线、Phase 3H 兼容性和下一步门禁评估。
- 正式默认继续使用确定性模板；下一项优先实验为 structured output first，并在后续加入 evidence citation。

## 下一步
由总控决定执行 structured output / retrieval-grounded explanation，或在当前作品集阶段暂停 LoRA。

## 注意事项
- LoRA 不参与 `risk_level`、`recommended_action` 或 `anomaly_types` 决策。
- 当前默认仍是确定性模板，LoRA 仅保留为 shadow / experimental。
- 第二轮逐样本 predictions、evaluation 和 manifest 不在当前 workspace，不能编造。

## 最后更新时间
2026-06-15
