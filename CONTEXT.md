# CONTEXT.md

## 当前目标
封板 Phase 3G.1 第二轮 LoRA 真实评测，并进入 Phase 3H 受控解释层。

## 当前进度
Phase 1 已封板：corrected pure LayoutLMv3 macro F1=0.8067。

Phase 2 已封板：真实审核工作流 baseline 已完成。

Phase 3G.1 已记录第二轮 ModelScope QLoRA 真实评测：唯一变量为 Phase 3F 事实约束型 Prompt 与统一 Gold Answer。fine-tuned 结果未通过 hard gate，LoRA 不接 API、不作为默认用户输出，第三轮训练暂停。

## 下一步
新开 Phase 3H.1 受控解释层实现对话：只实现 Canonical Audit Facts 适配、确定性模板解释、LoRA 输出 guard、fallback orchestrator 和 audit trace 的独立模块与测试。

## 注意事项
- Phase 1、Phase 2、API、Agent、Risk Engine、共享 schema 和数据库继续冻结。
- MVP 官方解释输出采用确定性模板。
- 当前 LoRA 只保留为 shadow/experimental controlled rewrite。
- 不启动第三轮训练，不接 API，不进入 HF Spaces、LangChain 对比、Docker、CI 或发布。

## 最后更新时间
2026-06-12
