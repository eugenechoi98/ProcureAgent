# DECISIONS.md

## 2026-06-13：统一作品集 Demo 采用三页签，重型模型默认展示真实离线 artifacts

稳定混合模式是作品集 Demo 的业务底座，不是最终唯一呈现。统一 Demo 冻结为 `Invoice Audit / Model Lab / Architecture` 三个页签：Invoice Audit 保留无 GPU、无 Key 的实时规则链；Model Lab 展示 LayoutLMv3 与两轮 LoRA 的真实离线指标、曲线、预测和失败分析；Architecture 解释模型、Agent 与确定性治理边界。

重型模型默认展示可复核的真实离线 artifacts，在线 LayoutLMv3、在线真实 LoRA、GPU Space 和 Phase 3I 只作为后续 optional feasibility。这样同时兼顾免费 CPU 环境稳定性、模型能力可见度、Agent 工程展示和 PyTorch、Transformers、LoRA/QLoRA、RAG、FastAPI、Docker、CI、Spaces 等简历筛选能力栈。

## 2026-06-12：本地 Gradio Demo 采用混合默认与显式静态 fallback

封板 Phase 2 可以稳定实时复现正常审核链，但不能在不改业务规则的前提下精确生成全部 13 个 canonical fixture。Demo 默认让 normal_invoice 运行实时混合链，其余不支持场景通过同一 Phase 3H renderer/guard/orchestrator 使用静态 fixture，并在页面明确标记 fallback，避免伪装成实时审核成功。

## 2026-06-12：首次公开 Demo 优先采用混合模式

当前 Git 不包含可部署的 Phase 1 微调 checkpoint，而 Phase 2、Canonical Facts、确定性模板和 13 个 Demo Cases 已能完全离线运行。首次公开 Demo 优先使用固定或预生成 ExtractedFields 驱动实时审核链，固定样例作为 fallback；在线 LayoutLMv3 留待模型资产和资源实测后再评估，真实 LoRA 继续关闭。

## 2026-06-12：Phase 3H 接入采用 AuditReport 内嵌解释 trace

现有 `audit_traces.step_name` 有固定 CHECK 约束，新增 explanation step 需要数据库变更。Phase 3H 选择把完整 explanation metadata 作为 `AuditReport` 可选字段写入现有 `audit_report_json`，既保留审计信息，也避免数据库 schema 和 migration。

## 2026-06-12：Phase 3H API 默认 template，模型模式必须显式启用

解释层只在 Phase 2 风险、动作和异常确定后运行。API 默认不配置 rewrite provider，shadow/experimental 只能显式选择并注入 provider；这样没有模型、网络或 GPU 时仍能稳定返回官方模板解释。

## 2026-06-12：Phase 3H 采用受控解释层，LoRA 不作为默认审核输出

第二轮 LoRA 真实评测未通过采购审核 hard gate：format、factual consistency、action consistency、anomaly coverage 和 hallucination 均不满足上线要求。因此 LoRA 不参与风险计算，不允许改变 `risk_level`、`recommended_action` 或 `anomaly_types`。

MVP 官方解释输出改为确定性模板，由 Phase 2 Canonical Audit Facts 驱动。当前 LoRA 仅保留为 shadow/experimental rewrite；未来只有同时通过 hard gate 和输出 guard，才可作为受控语言润色层。

第三轮训练暂停。HF Spaces Demo 和 LangChain Policy RAG 对比延后。Phase 3I 模型路线评估可作为后续可选项，不阻塞作品集交付。

## 2026-06-12：Phase 3G 第二轮训练输出必须独立成 run 目录
首轮真实 LoRA artifacts 已用于 Phase 3E 复盘，不能被第二轮覆盖。Phase 3F.1 增加 `PHASE3_ARTIFACT_DIR`，Notebook、bootstrap、base smoke、训练、评测和 manifest 统一使用当前 run 目录；第二轮推荐 `artifacts/phase3_runs/phase3g_second_lora_run/`。

## 2026-06-12：Phase 3F 用固定章节训练事实边界
首轮 LoRA 的主要失败是模型会补未知金额、GRN 和供应商关系。Phase 3F 不改训练超参，只把 system prompt 与 gold answer 统一成 `异常类型 / 事实边界 / 关键事实 / 缺失字段 / 禁止补全 / 审核结论` 六段，并在答案中显式示范缺失字段写未提供或缺失，让模型优先学习事实边界。

## 2026-06-12：Phase 3E 下一轮只调整事实约束与输出格式
首轮 fine-tuned 显著学会 recommended_action 和异常覆盖，但 factual_consistency 降到 0.80、hallucination_rate 升到 0.20，format_compliance 仍只有 0.15。下一轮优先只调整事实约束型 prompt 和统一结构化 `expected_explanation` 格式，不同时改 epoch、learning rate、LoRA r 或模型，避免无法判断收益来源。

## 2026-06-12：Phase 3D 训练门禁始终检查 CUDA runtime
`RUN_TRAINING=False` 只能表示不启动训练，不能表示训练环境可用。Phase 3D.4 将 `preflight_ready` 与 `training_ready` 分离：前者检查数据、依赖、模型和 Kernel，后者始终额外检查 CUDA、device count 和 bitsandbytes 4-bit 路径。Phase 3 GPU 依赖固定为 `torch==2.2.2+cu118`，避免浮动安装到需要更高 NVIDIA driver 的 Torch runtime。

## 2026-06-12：Phase 3 Notebook runtime guard 不覆盖 Terminal bootstrap
ModelScope Terminal 的环境变量不会自动继承到已启动的 Notebook Kernel。Phase 3D.3 为 Notebook 配置 ModelScope 默认模型目录和 Kernel Python，同时将 Notebook guard 写入 `notebook_runtime_guard.json`，Terminal bootstrap 继续保留 `environment_guard.json`，避免 Notebook 用缺配置报告覆盖正确的 Terminal preflight 证据。

## 2026-06-12：Phase 3 Notebook 使用统一 project-root resolver
ModelScope Notebook Kernel 的 cwd 可能是 `/mnt/workspace`，而仓库在 `/mnt/workspace/ProcureAgent`。Phase 3D.2 将项目根目录解析收口到 `procureguard.phase3.paths.resolve_project_root`，支持环境变量、cwd/parents、cwd 下的 `ProcureAgent`、Notebook 路径和 ModelScope 默认候选，避免 Notebook 手工写死路径。

## 2026-06-11：Phase 3D 独立环境先安装项目默认依赖
ModelScope `.venv-phase3` 先执行 `python -m pip install -e .`，再安装 `requirements/phase3-lora.txt`。这样 pydantic 等 ProcureGuard 默认依赖进入 Notebook 环境，同时 LoRA 重型依赖仍不混入默认后端依赖。

## 2026-06-11：Phase 3C 模型准备必须显式执行
Qwen2.5-0.5B-Instruct 不由 verify、bootstrap、base smoke 或 Notebook 静默下载。云端用户必须先用 `prepare_qwen_model.py --verify-only` 验证已有目录，或显式执行 `--download`，网络不可用时上传完整模型目录或压缩包，避免训练中途才暴露缺文件。

## 2026-06-11：Phase 3C 训练产物必须导出 manifest
首次 LoRA 训练后，Notebook 统一写出 base/fine-tuned predictions、evaluation report 和 `artifacts_manifest.json`。manifest 只记录文件路径、大小、SHA 和 adapter 目录清单，不提交模型权重或缓存，便于总控验收时核对真实产物。

## 2026-06-12：Phase 3 CUDA 训练环境固定 NumPy 1.x ABI
`torch==2.2.2+cu118` 与 bitsandbytes 4-bit QLoRA 路径依赖 NumPy 1.x ABI。Phase 3 GPU requirements 固定 `numpy==1.26.4`，Notebook guard 和 CUDA 诊断在训练前阻断 NumPy 2.x，避免模型加载或训练中途才出现 ABI 崩溃。

## 2026-06-11：Phase 3 Notebook 采用 bootstrap / verify / runtime context 分层
Phase 3B 将 Notebook 中零散的路径、依赖、数据 SHA、模型目录和输出目录检查沉淀为可复用脚本。bootstrap 负责创建 artifacts 并写 guard，verify 只读检查环境，runtime context 恢复当前 Kernel 的数据、prompt、训练参数和导出路径，避免云端手工补路径。

## 2026-06-11：Phase 3 base inference smoke 默认 dry-run
base 推理入口只生成可执行计划，只有显式 `--run` 且本地 Qwen 模型目录 guard 通过时才加载模型。这样可以先验证路径和数据口径，不在本地或验收阶段误触发大模型推理。

## 2026-06-11：Phase 3 小模型只解释确定性异常事实
风险等级、建议动作、金额匹配和异常类型继续由 Phase 2 确定性规则链产生。LoRA 模型只把这些输入事实整理成固定结构的审核说明，避免小模型改变审核结论或承担金额计算。

## 2026-06-11：Phase 3 使用独立数据契约和固定 synthetic split
不修改共享 Pydantic schema，训练样本放在 `procureguard.phase3` 独立契约中。数据使用 seed 42 生成 200 条 synthetic 样本，并固定为 160 train / 20 validation / 20 test，便于复现和公平比较 base 与 fine-tuned。

## 2026-06-11：Phase 3 评测以事实和动作一致性为主
base 与 fine-tuned 必须在同一 test split 上比较格式合规、事实一致、动作一致、多异常覆盖和幻觉率。没有真实推理文件时不生成指标，避免用主观文本观感或占位数字代替评测。

## 2026-06-11：LoRA GPU 依赖与默认后端环境隔离
默认 FastAPI 环境继续保持轻量。Phase 3 使用 `requirements/phase3-lora.txt` 和独立 GPU 虚拟环境；Notebook 优先 Unsloth，并保留 Transformers + PEFT + TRL fallback。

## 2026-06-11：corrected pure LayoutLMv3 作为 Phase 1 MVP 默认离线策略
同一 `local_validation_split_seed_42` 的 142 条 checkpoint inference 中，日期清洗使 date F1 从 0.1423 提升到 0.8764，corrected pure LayoutLMv3 macro F1 达到 0.8067，高于 Hybrid 的 0.7949。因此 Phase 1 MVP 默认采用 pure LayoutLMv3 离线抽取，Hybrid 只保留为 fallback 思路；该结果不是 official test，且尚未接入 API。

## 2026-06-11：LayoutLMv3 训练只允许加载 Safetensors
本地模型目录必须包含 `model.safetensors`，训练与验证显式使用 `use_safetensors=True` 和 `local_files_only=True`。不允许回退到 `pytorch_model.bin`，避免触发 `torch.load` 安全限制。

## 2026-06-11：首次 GPU 微调采用固定本地 validation split
首次 NVIDIA A10 微调结果使用 `local_validation_split_seed_42`，macro F1 为 0.6231。该结果用于 baseline 对比和工程决策，不表述为 official test。

## 2026-06-11：Phase 1 先保留 hybrid 离线策略
同一 validation split 上，LayoutLMv3 抽取 company/address/total、Regex 抽取 date 的 hybrid macro F1 为 0.7949。先将其作为可展示的离线方案，不接入 API；第二轮先用现有 checkpoint 验证日期重建修复，不调整 epoch 或学习率。

## 2026-06-11：GPU Notebook 将环境验证与 Kernel 状态恢复分离
bootstrap 子进程只负责依赖、路径、模型和 guard，不能承担 Notebook 变量注入。当前 Kernel 统一调用 runtime context 构建函数恢复标签、样本、processor、Torch、device 和训练参数，并在 Dataset 前一次性 preflight，避免逐个 NameError。

## 2026-06-11：GPU 训练环境以 Notebook Kernel 为唯一真源
ModelScope Terminal 与 Notebook Kernel 可能使用不同 Python 和 Torch。Phase 1 GPU 训练统一通过 `sys.executable` 安装和验证依赖，模型使用本地目录，processed JSONL 由 bootstrap 统一修复；只有训练 guard 通过后才允许进入训练。

## 2026-06-10：模型抽取依赖与默认后端依赖隔离
FastAPI 默认运行环境保持轻量，不强制安装 Torch、Transformers、PaddleOCR 和 PaddlePaddle。Phase 1 通过 extraction optional dependency group 安装模型依赖。LayoutLMv3 训练优先使用数据集提供的 OCR annotation，以单独评估字段抽取能力；PaddleOCR 用于端到端真实推理路径和 smoke 验证。

## 2026-06-10：Phase 1 先做独立抽取模块，不直接接入上传接口
Phase 2 后端真实规则链已经封板，Phase 1 只产出可替换 API 占位字段的模型抽取能力。这样可以先完成 OCR、LayoutLMv3、字段级 F1 和错误分析，不影响已通过的后端接口、工具签名和 Risk Engine。

## 2026-06-10：Agent 工具数量固定为 5 个
MVP 保持 5 个工具：查 PO、查收货、查重复、查政策、提交人工审核。这 5 个工具已经覆盖完整审核主链，不额外补没有明确业务价值的第 6 个工具。

## 2026-06-10：重复检测结果必须回写 ValidationResult
`check_duplicate_invoice` 的工具结果必须显式更新 `ValidationResult.duplicate_check`，否则 Risk Engine 会永远读到默认值，重复发票无法进入高风险分支。

## 2026-06-10：Policy RAG 使用 SQLite FTS5 和 mock 政策数据
Policy RAG 需要真实可检索的数据表与初始化数据，MVP 使用 `policy_documents` 加 `policy_fts`，先覆盖审批阈值、三单匹配、重复发票、数量误差、金额误差等演示场景。

## 2026-06-10：业务输出使用 AuditReport schema，不套 ContextPack
ContextPack 属于 ContextGraph Studio 的 AI Coding Agent 输出格式。ProcureGuard 是采购审核业务系统，最终结构化输出统一使用 `AuditReport` schema。

## 2026-06-10：重复发票采用确定性直接拒绝
重复发票属于高风险硬规则。检测到相同供应商与发票号重复提交后，将 `ValidationResult.duplicate_check` 写为 `False`，风险等级设为 `high`，建议动作设为 `reject`，不进入普通人工审核队列。
