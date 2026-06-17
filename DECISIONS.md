# DECISIONS.md

## 2026-06-18：Demo 自动采购上下文只使用预置 mock DB，不提升为真实 ERP

为降低演示用户门槛，`/api/mvp/audit/execute` 在缺少 `procurement_context` 时可以按 invoice_number 精确匹配、vendor keyword 备用匹配，从预置 demo mock DB 自动解析 PO/GRN；`/api/demo/audit` 固定走该 demo mode。该路径只解决作品集体验，不代表企业采购系统接入。所有 response 必须标注 `demo_mode`、`context_source`、`mock_data_notice` 和 `payment_authority=false`，风险等级和建议动作仍只由 Phase 2 deterministic rules 生成。

## 2026-06-17：Phase 4H 将 LoRA 收口为 Guarded Rewrite Runtime

两轮真实 LoRA 评测均未通过 hard gate，因此不能把 LoRA 提升为默认解释器或事实来源。Phase 4H 只允许 LoRA 在 Phase 2 已确定的 Canonical Audit Facts 和 deterministic template 之后生成语言改写候选；`guarded_lora` 只有 Guard PASS 才能成为最终解释，FAIL、provider 不可用、空输出、解析失败或高风险场景都回退 template。无论 PASS/FAIL，`risk_level`、`recommended_action`、`anomaly_types` 和 evidence 都不允许被解释层改写。

## 2026-06-17：Phase 4G-EXT 用单一 API 收口端到端 MVP

模块已经具备 image extraction、field confirmation 和 deterministic audit，但产品体验缺统一入口。新增 `/api/mvp/audit/execute` 作为编排层：image 和 candidates 必须先确认，Phase 2 只读取 confirmed fields，输出 AuditReport JSON、Markdown 和 trace。这样形成可运行 MVP 闭环，同时不把模型候选提升为审计事实。

## 2026-06-17：LoRA / Guard 在端到端链路中只影响解释，不影响审核结果

端到端 API 可以保留 explanation mode，但风险等级和建议动作在 LoRA 之前已经由 Phase 2 rules 生成。Guard failure 只改变解释来源和 fallback trace，不会回写 `risk_level`、`recommended_action` 或 validation evidence。

## 2026-06-17：Phase 4G 将 LayoutLMv3 隔离为字段候选生成器

LayoutLMv3 live extraction 已能输出字段候选，但模型候选不是审计事实。Phase 4G 要求所有字段先经过 human 或 simulated_human confirmation，只有 `ConfirmedAuditInput.confirmed_fields` 能作为 Phase 2 后续输入，避免 raw model output 直接触发采购风险判断。

## 2026-06-17：关键发票字段永远不能因模型高置信自动通过

`invoice_number`、`total_amount`、`vendor_name` 和 `invoice_date` 都会影响三单匹配、重复检测和金额风险，因此统一标记为 critical fields。它们必须人工确认或修正；confidence 只能用于 review UX，不得影响 `risk_level` 或 `recommended_action`。

## 2026-06-17：Phase 4F.2 从本地外部 artifacts 恢复微调 LayoutLMv3 bundle

`D:\ProcureAgent_LocalArtifacts\Phase1\layoutlmv3_best.zip` 是 Phase 1 训练时导出的真实 artifact，恢复后 checkpoint、processor、label map 和 manifest 通过检查，并完成 CPU live extraction。该 bundle 仍放在 ignored `artifacts/`，不提交权重；单样例成功只解锁 Phase 4G 字段确认设计，不代表 official test 或企业泛化。

## 2026-06-17：重训 fallback 只保留计划，不自动执行

虽然 Phase 4F.2 已找回 artifact，仍保留 rebuild plan 作为丢失时的最后手段。任何重训必须等用户明确说“允许重训”，并记录为 `retrained_layoutlmv3_v2`，不能覆盖原始 Phase 1 checkpoint 证据。

## 2026-06-15：Runtime bundle 只在 checkpoint label order 可证明时重建 label map

Phase 1 代码中的 BIO 标签可以生成 `label_map.json`，但只有 checkpoint `config.json` 的 `id2label` 与九标签顺序完全一致时才能组合使用。当前 checkpoint 缺失，因此 blocked bundle 不生成 label map，避免把旧权重和新标签定义无证据混配。

## 2026-06-15：公开 LayoutLMv3 base cache 不用于恢复微调 checkpoint

本地 base snapshot 包含权重和 processor，但没有 Phase 1 微调结果。它未来只能在确认 checkpoint processor 缺失时作为同一 base revision 的 processor 来源，不能替代 fine-tuned `model.safetensors`，也不能让 Phase 4F.1 从 blocked 变成 ready。

## 2026-06-15：Phase 4F 在缺微调 checkpoint 时保持 fail closed

当前本机只有公开 LayoutLMv3 base cache，没有与 Phase 1 指标对应的微调 checkpoint、saved processor 和 BIO label map。Base model 或 fake fixture 不能冒充真实产品抽取，因此 asset check 返回明确缺失状态，spike 不下载模型、不生成伪预测，Phase 4G 暂不启动。

## 2026-06-15：Live extraction confidence 使用真实 word-label softmax 并强制人工确认

字段存在预测 span 时，confidence 记录该字段 word-level 预测标签 softmax 的均值；没有 span 时保持 `null`，不编造分数。所有候选无论分数高低都必须标记人工确认，因为当前 confidence 未校准，且 OCR/抽取错误不能直接进入采购风险判断。

## 2026-06-15：产品目标纠正为开源可运行、真实用户可体验的受控审核 MVP

只展示离线模型证据不能验证用户输入到 AuditReport 的完整体验，直接建设认证、多租户、ERP 和 SLA 又会在核心链路未验证前扩大范围。因此后续先打通本地图片抽取、字段确认和确定性审核闭环，企业级能力不进入当前 Phase 4。

## 2026-06-15：Live LayoutLMv3 改为核心后续路径，先做本地 extraction spike

Phase 1 已有真实 checkpoint 和离线指标，但模型资产、OCR 输入、资源、延迟和错误契约尚未产品化。Phase 4F 先验证本地 OCR token+bbox 到 LayoutLMv3 字段候选，不立即改变 HF public Demo；候选经人工确认后才能进入 Phase 2。

## 2026-06-15：LoRA 只允许 guarded controlled rewrite

两轮 LoRA 未通过 hard gate，因此它只能在确定性事实和模板冻结后生成可选语言候选。任何 schema、事实、风险、动作、异常或引用校验失败都必须 fail closed 并返回 deterministic template，不能改变审核结论。

## 2026-06-15：LangChain comparison 排在核心图片审核闭环之后

当前 SQLite FTS5/BM25 Policy RAG 已是可解释正式主链。LangChain 只在 Phase 4I 使用相同本地语料和查询做可选对比，避免框架集成抢占 LayoutLMv3、字段确认和 Phase 2 集成的优先级。

## 2026-06-15：SQLite persistence 暂停为当前优先项

进程重启丢失 review 状态是已知限制，但当前更关键的产品缺口是用户无法从发票图片进入真实抽取与审核链。Persistence 在 Phase 4G 后按跨重启工作区需求重新评估，认证、多租户和生产数据治理继续后置。

## 2026-06-15：Phase 4D 使用应用进程内 store，不修改 Phase 2 schema

Manual Audit 的 Phase 4C 数据库是请求级临时数据库，强行复用 Phase 2 review 表会要求持久化整套临时上下文并扩大迁移范围。Phase 4D 选择进程内 store 保存本地 MVP 请求、结果和 reviewer metadata，满足导出与复核演示，同时明确服务重启即清空，不包装成生产审计留存。

## 2026-06-15：人工决定只做附加元数据，不覆盖规则结论

reviewer 可以 approve、reject 或 request_more_info，但原始 `risk_level`、`recommended_action`、policy flags 和 evidence 始终保留。这样可以展示人机复核闭环，又不会混淆“确定性系统判断”和“本地人工意见”。

## 2026-06-15：导出同时提供 JSON 与 Markdown，并强制带非付款边界

JSON 服务机器读取，Markdown 服务面试展示和本地审核说明。两种格式都包含来源、fallback、review 和 `payment_authority=false`，避免导出文件被误认为付款凭证、合规批准或企业采购记录。

## 2026-06-15：Manual Audit 使用请求级内存 SQLite 注入显式 mock context

现有五个工具和 AgentInvoiceProcessor 都依赖 SQLite 查询。为复用真实 Phase 2 主链且不污染默认 seed，每次请求创建独立内存数据库，只写入用户显式提供的 PO、GRN、重复标志和 mock policies，请求结束即关闭。这样无需修改工具签名，也不会影响 HF Demo 或已有数据库。

## 2026-06-15：Manual Audit 只开放 deterministic template

真实用户最小输入流的目标是验证字段、采购上下文和规则审核闭环，不是继续模型实验。API 固定 `explanation_mode=template`，不暴露 shadow 或 experimental，确保模型不能进入正式结果路径，也避免把 Phase 3 离线实验误写成产品能力。

## 2026-06-15：产品响应单独声明来源和付款权限

AuditReport 保持共享业务契约不变，ManualAuditResponse 额外返回 manual input、explicit mock context、deterministic rules、deterministic template、无 live model 和无 payment authority 标签。这样既不破坏 Phase 2 契约，又让试用者能直接判断每类结果来自哪里。

## 2026-06-15：开源 sample 使用内存 SQLite 和现有确定性主链

clean-clone smoke 只读取 synthetic 结构化发票字段，并复用现有 mock PO/GRN、Policy RAG、Risk Engine 和 deterministic template。这样陌生开发者可以在无模型、无网络、无本地数据残留的情况下验证真实业务主链，同时不会把 sample 误写成图片在线推理或企业数据。

## 2026-06-15：环境样例只公开当前代码真实支持的配置

当前应用只读取 `DATABASE_PATH` 和 `UPLOAD_DIR`，尚未实现统一的环境标记、Demo mode 或日志级别配置。`.env.example` 不主动新增未生效变量，避免让开源用户误以为项目已经具备生产环境隔离或日志治理。

## 2026-06-15：MIT 仅覆盖仓库代码，不覆盖外部数据与模型资产

SROIE、Voxel51 scanned_receipts、CORD 和基础模型保留原发布方许可，模型权重、checkpoint、adapter、缓存和原始训练 artifacts 继续不提交 Git。这样可以开放工程代码，同时不错误转授权第三方数据和模型资产。

## 2026-06-15：真实用户 MVP 先采用手动字段输入，不以在线 LayoutLMv3 为前置

当前 Phase 2 规则链已经能验证三单匹配、Policy RAG、风险判断和人工审核价值，而在线 OCR/LayoutLMv3 仍涉及权重托管、资源、延迟、文件安全和泛化风险。先用手动发票字段与显式 mock PO/GRN 打通用户流程，可以更低成本验证产品价值；在线模型推理延后为可选 Phase 4F。

## 2026-06-15：开源发布先完成 Quickstart 与安全边界，再扩展产品功能

当前仓库具备 Demo、CI 和测试基础，但缺干净 clone Quickstart、环境样例、许可、统一 sample、隐私说明和分层测试入口。Phase 4B 优先补齐这些开源基础，避免把“作者机器可运行”误判为“陌生开发者可复现”，也避免真实敏感发票被误上传到研究原型。

## 2026-06-15：HF Space 与真实用户 MVP 保持两条产品路径

HF Space 继续作为 public portfolio demo，展示离线模型证据、mock 采购上下文和受控审核架构；真实用户 MVP 另行提供手动输入、规则审核、报告导出和人工复核。这样既保留稳定公开展示，也不会把固定案例或离线 artifacts 包装成生产能力。

## 2026-06-15：Phase 3K citation 必须由上游证据目录约束

Evidence Catalog 只从 Canonical Audit Facts 构造，bullet 的 claim type、关键实体和 evidence ID 必须同时匹配；引用存在但内容不匹配仍然拒绝，任何失败继续回退确定性模板。这样可增加解释可追溯性，但不把规则校验夸大为通用语义蕴含，也不改变正式默认解释路径。

## 2026-06-15：Phase 3J 结构化解释采用 exact-match 与 fail-closed

Structured Output First baseline 对 `risk_level`、`recommended_action`、`anomaly_types` 和 `missing_fields` 采用上游事实 exact-match，不允许用子集掩盖多异常漏项；bullet 必须绑定允许 evidence ID，任何 schema、事实或引用失败都回退现有确定性模板。这样可以验证结构化路线的可审计性，同时不改变 Phase 3H 正式默认路径，也不把离线 rule-only 实验包装成模型能力。

## 2026-06-14：最终作品集定位采用受控 Agent，不补 LLM Tool Router

采购审核中的 PO、GRN、重复检测、政策查询和人工审核流转存在固定业务依赖，强行让 LLM 自主选择工具顺序只会制造不可解释的伪自由度。最终作品集统一定位为“受控采购发票审核 Agent”：LayoutLMv3 负责字段抽取，五个工具负责证据查询，确定性风险引擎决定风险等级和建议动作，LoRA 只作为受控解释候选，并由 Guard / Fallback 阻止未知事实或结论篡改。

## 2026-06-13：公网部署验收区分机器 smoke 与人工视觉检查

Hugging Face Space 已运行在 CPU Basic，公开 HTTP、Gradio config 和审核 API 已通过，但当前自动化视觉浏览器加载超时。因此部署报告保守保持 `online_deployment_verified=false` 和 `manual_browser_check_required=true`，直到用户完成一次实际页面视觉检查。公网 Demo 只展示确定性审核链、真实离线 Model Lab artifacts 和 Architecture，不把它表述为在线模型推理或生产服务。

## 2026-06-13：工程收口保持正式主链与可选能力隔离

SQLite FTS5 / BM25 继续作为 Policy RAG 正式主链，LangChain 仅使用本地政策语料做可选兼容 benchmark，避免为简历能力项改变已封板业务行为。Docker 默认镜像只安装 Demo extra，CI 才显式安装 Demo、LangChain 和测试 extras，继续隔离模型训练依赖。当前主机没有 Docker CLI，因此只声明配置就绪，不声明容器 runtime 通过；本地 release readiness 也不等于 Hugging Face 在线部署验证。

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

## 2026-06-15：Phase 3I 优先结构化解释，不继续自由文本试参
Phase 3I 推荐保持确定性模板为正式默认，并把 Structured Output First 作为唯一优先实验，后续再加入 evidence citation；两轮自由文本 LoRA 已证明低训练 loss 不能保证事实、动作、异常覆盖和格式稳定，且第二轮缺少本地逐样本 artifacts，因此暂不启动第三轮训练或更换大模型，LoRA 仍不作为默认正式解释器。

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
# Batch H0 端到端证据必须逐字段标注来源

SROIE Task 3 只提供 `company/address/date/total` 四字段，不能把为了进入采购审核链而补充的 invoice number、PO、GRN 写成图片抽取结果。Batch H0 因此把模型预测字段和 mock 采购上下文分开记录，并要求 manifest 同时保存允许与禁止的 claim。这样既能复用真实 Phase 2 引擎，又不会制造一条看似完整但来源混乱的证据链。

## Batch H1 公网页面优先读取已验收证据包

公网 CPU Space 不上传模型权重，也不把选择案例包装成实时模型推理。案例 A/B 直接展示 H0 已提交的图片、OCR、离线 checkpoint 预测和 Phase 2 结果；案例 C 展示真实离线 LoRA artifact 与 Guard 执行结果。SROIE 不包含企业 PO/GRN，因此 A/B 使用明确标注的 mock 采购上下文，且公网 Demo 不开放任意图片上传。这样能把真实工程链路讲完整，同时保持 CPU-only 稳定性、来源边界诚实和证据可复核。
