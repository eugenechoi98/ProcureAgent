# CONTEXT.md

## 当前目标
完成 Phase 3B LoRA GPU Notebook 可复现运行准备。

## 当前进度
- Phase 1 已封板，默认离线策略为 `pure_layoutlmv3_date_path`，尚未接入 API。
- Phase 2 已封板，真实确定性审核链保持不变。
- Phase 3A 已通过验收：独立数据契约、200 条 synthetic 数据、统一评测脚本和 LoRA Notebook 骨架已完成。
- Phase 3B 正在收口 Notebook bootstrap、verify、runtime context、路径解析、数据 SHA guard、模型目录 guard 和 base inference smoke。
- 尚未执行 Qwen2.5-0.5B-Instruct LoRA GPU 训练，也没有 fine-tuned 指标。

## 下一步
完成 Phase 3B 本地可复现准备验收后，回到审查与总控对话确认是否进入云端 base inference 和 LoRA 训练。

## 注意事项
- Phase 3 模型只生成异常说明，不计算金额、不决定风险等级、不改变建议动作。
- Phase 3 数据全部为固定 seed synthetic 数据，不包含真实企业数据。
- LoRA 训练依赖与默认 FastAPI 环境隔离。
- base inference smoke 默认 dry-run，只有显式开关和本地模型目录可用时才加载模型。
- checkpoint、adapter、模型缓存和本地 artifacts 不提交 Git。

## 最后更新时间
2026-06-11
