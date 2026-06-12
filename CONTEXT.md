# CONTEXT.md

## 当前目标
完成 Phase 3H.1a 受控解释层最小安全修复。

## 当前进度
Phase 1 已封板：corrected pure LayoutLMv3 macro F1=0.8067。

Phase 2 已封板：真实审核工作流 baseline 已完成。

Phase 3G.1 已记录第二轮 ModelScope QLoRA 真实评测：fine-tuned 结果未通过 hard gate，LoRA 不接 API、不作为默认用户输出，第三轮训练暂停。

Phase 3H.1a 已将 Canonical Audit Facts 改为递归不可变快照，并将 rewrite 运行、契约解析、非法输出和 guard 异常统一 fail-closed 回退确定性模板。固定 guard 场景和审计字段已补自动回归测试。

## 下一步
回到审查与总控对话验收 Phase 3H.1a；API 接入仍未批准。

## 注意事项
- Phase 1、Phase 2、API、Agent、Risk Engine、共享 schema 和数据库继续冻结。
- MVP 官方解释输出采用确定性模板。
- 当前 LoRA 只保留为 shadow/experimental controlled rewrite。
- 当前 guard 是保守的结构化规则 guard，不是生产级语义校验器。
- Phase 3H.1 未接 API、未改 Phase 1/Phase 2 主链、未启动 GPU。
- 不启动第三轮训练，不接 API，不进入 HF Spaces、LangChain 对比、Docker、CI 或发布。

## 最后更新时间
2026-06-12
