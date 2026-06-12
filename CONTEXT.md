# CONTEXT.md

## 当前目标
完成 Demo Deployability Review 和本地离线 readiness 检查。

## 当前进度
Phase 1 已封板：corrected pure LayoutLMv3 macro F1=0.8067。

Phase 2 已封板：真实审核工作流 baseline 已完成。

Phase 3G.1 已记录第二轮 ModelScope QLoRA 真实评测：fine-tuned 结果未通过 hard gate，LoRA 不接 API、不作为默认用户输出，第三轮训练暂停。

Phase 3H.2 已在 Phase 2 结果确定后接入 Canonical Facts、默认模板和显式 shadow/experimental 模式。AuditReport 增加可选 explanation metadata，解释 trace 采用返回结果方案 B，不修改数据库。

Phase 3H.3 已新增 API/服务端到端测试和 13 个固定离线 Demo Cases，不依赖 GPU、网络、Qwen 或 ModelScope。

Phase 3H 已合并并 push 到 main。当前只评估固定样例、混合模式和完整在线模式的部署可行性，尚未创建 Hugging Face Space。

已新增本地只读 readiness 检查，验证 13 个固定 Demo Cases 和无 Key、无网络、无 GPU、无 Qwen/LoRA 的默认演示条件。

## 下一步
完成独立评估分支文档、readiness 脚本、测试和 push 后回总控验收，不合并评估分支。

## 注意事项
- Phase 1、Phase 2 决策、Agent、Risk Engine 和数据库继续冻结；API 只增加向后兼容 explanation 输出。
- MVP 官方解释输出采用确定性模板。
- 当前 LoRA 只保留为 shadow/experimental controlled rewrite。
- 当前 guard 是保守的结构化规则 guard，不是生产级语义校验器。
- API 默认解释为确定性模板，真实 LoRA provider 未配置。
- Phase 2 风险、动作、异常和工具逻辑未修改。
- 当前不需要 API Key。
- readiness 只表示本地离线演示准备情况，不代表线上部署通过。
- 不启动第三轮训练，不接真实 LoRA provider，不创建 HF Space，不进入 LangChain 对比、Docker、CI 或发布。

## 最后更新时间
2026-06-12
