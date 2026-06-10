# CONTEXT.md

## 当前目标
在完整 runtime context 下运行 LayoutLMv3 GPU fine-tuning。

## 当前进度
- Phase 2 已封板。
- Phase 1A-D 已完成：OCR baseline、Task 3 数据、BIO alignment、Dataset、DataLoader、单 batch forward 和 PaddleOCR smoke。
- Phase 1E.1 已完成可复现 bootstrap、依赖、本地模型和 JSONL 路径修复。
- Notebook 已新增当前 Kernel hydrate 和统一 preflight，训练变量不再依赖子进程注入。
- 当前尚未运行完整 fine-tuning。

## 下一步
用户重启 ModelScope Kernel，顺序运行 bootstrap、hydrate、preflight；确认 `training_guard_passed=true` 和 `missing_names=[]` 后再训练。

## 注意事项
- 当前 baseline macro F1 为 0.4387。
- validation 使用 local_validation_split_seed_42，不是 official test。
- Terminal 与 Notebook Kernel 可能不同，训练环境以 Kernel 的 `sys.executable` 为准。
- bootstrap 验证外部环境，hydrate 恢复当前 Kernel 的 Python 训练上下文。
- 网络受限时使用本地模型目录和上传的 processed JSONL。
- checkpoint、模型权重和真实数据不提交 Git。
- 模型训练完成后再决定是否接入 API。

## 最后更新时间
2026-06-11
