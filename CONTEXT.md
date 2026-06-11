# CONTEXT.md

## 当前目标
推进 Phase 3C ModelScope 云端 preflight、base inference 与首次 LoRA 训练。

## 当前进度
- Phase 1 已封板，默认离线策略为 `pure_layoutlmv3_date_path`，尚未接入 API。
- Phase 2 已封板，真实确定性审核链保持不变。
- Phase 3A 已通过验收：独立数据契约、200 条 synthetic 数据、统一评测脚本和 LoRA Notebook 骨架已完成。
- Phase 3B 已通过验收：bootstrap、verify、runtime context、数据 SHA guard、模型目录 guard 和 base inference smoke dry-run 已完成。
- Phase 3C 已补齐 Notebook 训练后导出闭环：base/fine-tuned predictions、evaluation report 和 artifacts manifest。
- Phase 3C.1 已新增显式 Qwen 模型准备脚本和 ModelScope Kernel 注册说明；模型不会由 guard 静默下载。
- Phase 3D.1 已收口 ModelScope `.venv-phase3` 安装顺序：先 `pip install -e .` 安装项目默认依赖，再安装 Phase 3 LoRA 依赖；verify 会提前检查 pydantic。
- Phase 3D.2 已统一 Phase 3 project-root resolver，兼容 ModelScope Kernel cwd 为 `/mnt/workspace` 且仓库在 `/mnt/workspace/ProcureAgent`。
- Phase 3D.3 已收口 Notebook 环境变量继承问题：Notebook 默认使用 ModelScope Qwen 模型目录和 Kernel Python，并写独立 `notebook_runtime_guard.json`。
- 本地已通过 Phase 3 专项测试和全量测试；真实 ModelScope CUDA verify、base smoke `--run` 和 LoRA 训练尚未执行。

## 下一步
用户在 ModelScope 按 runbook 执行 git pull，保留现有 `.venv-phase3`、Qwen 模型目录和 base smoke 产物，重启 Notebook Kernel 后从第一格重新运行配置、guard 和 runtime context。

## 注意事项
- Phase 3 模型只生成异常说明，不计算金额、不决定风险等级、不改变建议动作。
- Phase 3 数据全部为固定 seed synthetic 数据，不包含真实企业数据。
- LoRA 训练依赖与默认 FastAPI 环境隔离。
- base inference smoke 默认 dry-run，只有显式 `--run` 和本地模型目录可用时才加载模型。
- checkpoint、adapter、模型缓存和本地 artifacts 不提交 Git；adapter 压缩包保存到仓库外本地 artifacts 目录。

## 最后更新时间
2026-06-11
