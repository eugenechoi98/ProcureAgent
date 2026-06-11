# CONTEXT.md

## 当前目标
完成 Phase 1 文档与证据封板。

## 当前进度
- Phase 2 已封板。
- Phase 1A-D 已完成：OCR baseline、Task 3 数据、BIO alignment、Dataset、DataLoader、单 batch forward 和 PaddleOCR smoke。
- Phase 1E.1 已完成可复现 bootstrap、依赖、本地模型和 JSONL 路径修复。
- Notebook 已新增当前 Kernel hydrate 和统一 preflight，训练变量不再依赖子进程注入。
- 首次 NVIDIA A10 完整 fine-tuning 已完成，best epoch=5，token F1=0.8647，field macro F1=0.6231。
- Hybrid 离线 macro F1=0.7949；日期金标 BIO 重建错误经清洗从 122 降至 25，与 25 个 alignment miss 对齐。
- Phase 1F 验收修复已完成，报告字段和本地数据忽略规则已收口。
- Phase 1G 已完成 142 条 checkpoint validation inference，date F1 从 0.1423 提升到 0.8764。
- 修复后 pure LayoutLMv3 macro F1=0.8067，高于 Hybrid macro F1=0.7949。
- Phase 1 MVP 默认离线策略为 `pure_layoutlmv3_date_path`，Hybrid 仅保留为 fallback 思路。

## 下一步
完成本轮证据提交后结束 Phase 1，回到总控对话决定后续阶段。

## 注意事项
- 当前 baseline macro F1 为 0.4387。
- checkpoint inference 属于 `local_validation_split_seed_42` 离线评测，不是 official test。
- Phase 1 模型抽取尚未接入 API。
- 本地模型必须包含 model.safetensors，不允许回退 pytorch_model.bin。
- Terminal 与 Notebook Kernel 可能不同，训练环境以 Kernel 的 `sys.executable` 为准。
- bootstrap 验证外部环境，hydrate 恢复当前 Kernel 的 Python 训练上下文。
- 网络受限时使用本地模型目录和上传的 processed JSONL。
- checkpoint、模型权重、真实数据和本地 artifacts 不提交 Git。

## 最后更新时间
2026-06-11
