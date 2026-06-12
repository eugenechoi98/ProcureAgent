# CONTEXT.md

## 当前目标
复盘 Phase 3E 首轮 LoRA 真实训练与 base vs fine-tuned 评测结果，设计下一轮单变量实验。

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
- Phase 3D.4 已将 `preflight_ready` 与 `training_ready` 分离，训练门禁始终检查 CUDA、device count 和 bitsandbytes，并固定 Phase 3 Torch 为 `2.2.2+cu118`。
- Phase 3D.5 已固定 `numpy==1.26.4`，并将 NumPy ABI 兼容性纳入 CUDA runtime 诊断和 Notebook 训练门禁。
- Phase 3E 已读取仓库外首轮真实 artifacts，生成按异常类型拆分、hallucination 清单、format 失败分布和下一轮 hard gate 复盘报告。

## 下一步
回到总控审查 Phase 3E 复盘。下一轮只允许先改“事实约束型 prompt + 统一结构化 expected_explanation 数据格式”这一主变量，再由用户在 ModelScope 亲自启动第二轮 GPU 训练。

## 注意事项
- Phase 3 模型只生成异常说明，不计算金额、不决定风险等级、不改变建议动作。
- Phase 3 数据全部为固定 seed synthetic 数据，不包含真实企业数据。
- LoRA 训练依赖与默认 FastAPI 环境隔离。
- base inference smoke 默认 dry-run，只有显式 `--run` 和本地模型目录可用时才加载模型。
- checkpoint、adapter、模型缓存和本地 artifacts 不提交 Git；adapter 压缩包保存到仓库外本地 artifacts 目录。
- 首轮 adapter 与 checkpoints 保存在 `D:\ProcureAgent_LocalArtifacts\Phase3\phase3_first_lora_run\phase3`，不提交 Git。

## 最后更新时间
2026-06-12
