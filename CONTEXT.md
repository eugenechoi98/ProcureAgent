# CONTEXT.md

## 当前目标
使用现有最佳 checkpoint 对比日期旧/新重建的真实 validation F1。

## 当前进度
- Phase 2 已封板。
- Phase 1A-D 已完成：OCR baseline、Task 3 数据、BIO alignment、Dataset、DataLoader、单 batch forward 和 PaddleOCR smoke。
- Phase 1E.1 已完成可复现 bootstrap、依赖、本地模型和 JSONL 路径修复。
- Notebook 已新增当前 Kernel hydrate 和统一 preflight，训练变量不再依赖子进程注入。
- 首次 NVIDIA A10 完整 fine-tuning 已完成，best epoch=5，token F1=0.8647，field macro F1=0.6231。
- Hybrid 离线 macro F1=0.7949；日期金标 BIO 重建错误经清洗从 122 降至 25，与 25 个 alignment miss 对齐。
- Phase 1F 验收修复已完成，报告字段和本地数据忽略规则已收口。
- Phase 1G 单命令 checkpoint inference 已准备，本机无 checkpoint，实际恢复幅度等待 ModelScope 执行。

## 下一步
在 ModelScope 执行 `compare_date_reconstruction.py`，回传三个 checkpoint inference 报告文件。

## 注意事项
- 当前 baseline macro F1 为 0.4387。
- validation 使用 local_validation_split_seed_42，不是 official test。
- 首轮纯 LayoutLMv3 date F1=0.1423，主要风险在 alignment/reconstruction，不先调 epoch 或学习率。
- 本地模型必须包含 model.safetensors，不允许回退 pytorch_model.bin。
- Terminal 与 Notebook Kernel 可能不同，训练环境以 Kernel 的 `sys.executable` 为准。
- bootstrap 验证外部环境，hydrate 恢复当前 Kernel 的 Python 训练上下文。
- 网络受限时使用本地模型目录和上传的 processed JSONL。
- checkpoint、模型权重和真实数据不提交 Git。
- 模型训练完成后再决定是否接入 API。

## 最后更新时间
2026-06-11
