# Phase 4A Productization & Open-source Gap Audit

## 1. 审计结论

ProcureGuard AI 已具备可复核的作品集 Demo、确定性采购审核主链、人工审核接口、审计轨迹和模型实验治理证据，但尚未达到“陌生开发者从干净仓库稳定运行”或“真实用户完成一次受控审核”的产品级标准。

当前最准确的定位是：**可公开展示、可本地验证核心规则链的研究型受控采购审核 Agent 原型**。它不是生产系统，也不能作为付款依据。

### 当前成熟度

| 能力 | 状态 | 判断 |
| --- | --- | --- |
| 作品集展示 | 已完成 | HF Space 能展示端到端证据链和治理边界 |
| Phase 2 规则审核 | 已完成 | FastAPI、SQLite、五工具、Risk Engine、AuditReport 可测试 |
| 本地 Demo | 基本完成 | 已有 Gradio 入口，但偏作品集案例，不是用户录入工作台 |
| 开源可运行 | 部分完成 | 有安装和测试命令，但缺干净 clone Quickstart、环境样例、许可与分层验证入口 |
| 真实用户 MVP | 未完成 | 缺手动字段/采购上下文录入、报告导出和清晰审核工作台 |
| 在线模型推理 | 未完成且不阻塞近期 MVP | LayoutLMv3、LoRA、3J、3K 均未接生产 API |
| 生产可用 | 未完成 | 缺隐私、认证、租户、迁移、错误契约、运行运维等能力 |

## 2. 最高优先级 Top 5

1. **干净 clone Quickstart 与仓库卫生**：补齐 `.env.example`、最小样例、API 启动命令、分层测试命令、许可、数据归属和隐私说明。
2. **真实用户最小输入流**：先支持手动填写发票字段和显式配置 mock PO/GRN，再调用现有 Phase 2 规则链；不要把图片上传等同于在线抽取。
3. **安全边界与状态可见性**：明确“不得上传敏感发票、不能作为付款依据、规则结论不可被模型覆盖”，并统一 live/offline/mock/fallback/failure 状态。
4. **AuditReport 导出与人工复核闭环**：支持 JSON/Markdown 导出、审核备注、决策状态和审计日志导出。
5. **API 产品契约**：补充明确 request/response schema、稳定错误码、数据库初始化/迁移说明、demo reset 和 sample tenant 边界。

在线 OCR / LayoutLMv3 不在 Top 5。手动字段输入已经足以让真实用户验证 Phase 2 的业务价值，且风险更低、成本更可控。

## 3. 真实用户可用性差距

### 3.1 现在已完成

- FastAPI 有健康检查、发票上传、单笔/列表查询、trace 查询、人工审核队列和审核决策接口。
- 上传接口能保存文件，并用受控 `explanation_mode` 运行现有审核链。
- 本地 Gradio 与 HF Space 能展示固定案例、AuditReport 和模型离线证据。
- Phase 2 能基于预生成/占位 `ExtractedFields`、mock PO/GRN 和政策数据生成确定性结果。
- 中高风险可进入人工审核队列，已有 reviewer comment 数据字段与决策接口。

### 3.2 当前真实用户能输入什么

- API 用户可上传文件，并选择 `template|shadow|experimental` 解释模式。
- 开发者可通过 fixture、mock 数据或代码路径提供预生成字段。
- Demo 用户主要选择已打包案例；公网入口不接受任意图片并现场运行 LayoutLMv3。

当前“上传成功”不代表“图片被真实模型解析”。这必须在 UI、API 和 README 中持续明确。

### 3.3 只能查看离线证据、不能真实在线运行的部分

- LayoutLMv3 checkpoint inference 与字段级指标。
- 两轮 Qwen2.5-0.5B LoRA 结果和真实离线 artifact。
- Phase 3J Structured Output First baseline。
- Phase 3K Evidence Citation baseline。
- H0/H1 的 A/B 模型预测证据包和 C 的 LoRA Guard/Fallback artifact。

### 3.4 MVP 能力分级

| 能力 | 分类 | 原因 |
| --- | --- | --- |
| 手动输入发票字段 | 短期必须补 | 最低成本打通真实用户输入到规则审核输出 |
| 手动配置 PO/GRN mock context | 短期必须补 | 让三单匹配可解释、可重复试用 |
| 导出 AuditReport JSON/Markdown | 短期必须补 | 用户需要带走结果，也便于审计和反馈 |
| 人工审核备注与决策 | 已有后端，短期补 UX | 接口已存在，但缺统一用户工作台 |
| 上传图片但不在线推理 | 中期可选 | 只有在明确“附件留存/人工录入”时才有价值 |
| 上传图片并在线 OCR/LayoutLMv3 | 暂缓至 Phase 4F | 依赖权重、OCR、算力、延迟、安全和质量治理 |
| 在线 LoRA | 暂缓 | 未通过 hard gate，不能进入正式路径 |

## 4. 开源仓库可运行性差距

### 4.1 已有基础

- `pyproject.toml` 区分默认、demo、langchain、extraction/phase1、test 依赖。
- README 有本地 Demo 安装、全量 pytest、Phase 1/3 专项命令和 release readiness。
- CI 执行 `pip check`、离线 smoke、专项测试、release readiness 和全量测试。
- `.gitignore` 已排除数据库、上传文件、模型权重、checkpoint、adapter、缓存和本地 artifacts。
- Docker Compose 与 Dockerfile 已存在，但当前机器未验证 Docker runtime。

### 4.2 主要缺口

- README 没有一段从“创建 `.venv`”开始的统一 Quickstart，也没有明确 FastAPI 启动、`/docs`、首个请求和期望响应。
- 仓库没有 `.env.example`，虽然配置只需要 `DATABASE_PATH`、`UPLOAD_DIR`，但陌生用户无法一眼知道可配置项。
- 缺面向用户的最小发票 + PO + GRN sample bundle 和一条可复现审核命令。
- 测试入口没有稳定分层命名：`smoke`、`phase1`、`phase2`、`phase3`、`full`。
- README 没有把本地 `pip check` 作为 Quickstart 验收步骤。
- 缺根目录 LICENSE；数据集归属已有摘要，但缺完整 dataset attribution、使用限制和隐私说明。
- 模型权重/adapter/dataset 的“不提交 Git”规则散落在 `.gitignore` 和运行手册，需集中到开源说明。
- README 存在 Windows 绝对路径形式的链接，不适合作为 GitHub 跨环境链接。
- 根目录存在大型 SROIE 压缩包；即使被 ignore，也应在发布审查中确认未被 Git 追踪，并说明下载方式。

### 4.3 建议测试分层

| 层级 | 建议内容 |
| --- | --- |
| smoke | import、health、sample audit、JSON parse、demo readiness |
| phase1 | 数据契约、baseline、reconstruction、离线 artifact 校验；GPU/live inference 单独标记 |
| phase2 | API、共享契约、规则、Policy RAG、人工审核 |
| phase3 | dataset/evaluator、Guard/Fallback、3J/3K 离线 baseline |
| full | `tests/` 全量 CPU-only；GPU Notebook 不放入默认 full |

## 5. 产品安全与边界差距

### 已明确

- LLM 不决定 `risk_level`。
- `recommended_action` 来自确定性规则。
- A/B 的 PO/GRN 是 mock 采购上下文。
- C 使用真实离线 LoRA artifact，但输入是 synthetic evaluation fixture。
- deterministic template 是正式默认；LoRA、3J、3K 不接生产 API。

### 必须补齐

- 在 README、用户入口和 API 文档统一加入：不要上传真实敏感发票；仅供研究/演示；不能作为财务付款依据。
- 定义上传文件的保留时间、存储位置、删除方式、日志中是否出现原始字段；当前没有产品级隐私策略。
- 模型输出只能写入 additive explanation 字段，服务端必须忽略其对风险、动作和异常类型的覆盖尝试。
- 对外统一状态：`deterministic_live`、`offline_artifact`、`mock_context`、`static_fallback`、`guard_rejected`、`processing_failed`。
- 提供 AuditReport 与 Audit Trace 的导出；当前 trace 可查询，但没有用户级导出流程。
- 对 fallback 区分原因：provider unavailable、parse error、guard rejected、static demo fallback、upstream processing failure。

## 6. API 与工程产品化差距

### 当前判断

- FastAPI 对早期 MVP 足够，但接口更接近工程验证，不是稳定公共 API。
- Pydantic 模型和 FastAPI 自动 `/docs` 提供基础 OpenAPI，但 README 未把它作为正式契约入口，也没有版本化说明。
- HTTP 400/404/409/422/500 已使用，但错误体只有 `detail`，缺稳定 `error_code`、field errors、trace ID 和可恢复提示。
- 人工审核后端闭环存在，但缺用户工作台、权限和并发策略。
- 数据库由启动逻辑初始化，缺显式初始化命令、schema version、migration 和备份/恢复说明。
- SQLite 仍适合单机、单用户或小规模 MVP；在并发、多租户、权限和长期审计出现前无需切 PostgreSQL。

### 后续需要

- 新增版本化请求模型，支持手动字段和受控 mock procurement context。
- 明确 OpenAPI 示例、成功/失败响应和字段来源标签。
- 建立错误码表，例如 `INVALID_INPUT`、`DUPLICATE_INVOICE`、`PO_NOT_FOUND`、`PROCESSING_FAILED`。
- 提供 `demo mode`、sample tenant 或隔离 sample database，以及幂等 reset/seed 脚本。
- 增加 AuditReport JSON/Markdown 导出；PDF 可后置。
- Docker 需要在 Phase 4E 验证构建、健康检查、volume、非 root、资源限制和升级路径，本轮不实现。

## 7. 模型能力产品化差距

### LayoutLMv3

近期 MVP 不应把在线 LayoutLMv3 设为 blocker。先用手动字段输入 + Phase 2 规则链验证用户流程和报告价值。

若进入 Phase 4F，需要解决：

- checkpoint 的合法托管、版本和 SHA；模型权重不能直接提交 Git。
- PaddleOCR/图像预处理依赖、CPU/GPU 兼容和系统库。
- 冷启动、下载时间、内存、吞吐、超时和并发。
- 图片格式、大小、恶意文件、OCR 失败、低置信字段和人工纠正。
- 当前 0.8067 是固定本地 validation split 的 corrected offline checkpoint 指标，不是 official test，也不是企业发票泛化证明。

### LoRA、Structured Output、Evidence Citation

- LoRA 继续保持 shadow/research；第二轮未通过 hard gate。
- Phase 3J/3K 只作为离线治理证据，证明 validator/fallback 流程，不证明 LLM 上线能力。
- adapter、checkpoint、base model、模型缓存、原始训练运行目录和受许可限制的数据集不能提交 Git。
- 可提交轻量指标、manifest、哈希、精选脱敏预测和失败分析，但必须标明来源与限制。

### 不能被单样本误导的指标

- LayoutLMv3 数据集级 Macro F1、Date F1 和字段泛化能力。
- LoRA factual/action/anomaly/format hard gate。
- Guard、Structured Output、Citation 对任意自然语言的覆盖能力。
- 端到端延迟、失败率、人工复核率和真实企业准确率。

## 8. Demo 与真实产品的关系

- HF Space 是 public portfolio demo，不是完整生产产品。
- 它展示真实离线模型证据和轻量规则链，但不代表真实企业采购系统。
- A/B 使用 mock PO/GRN；C 使用 synthetic facts。
- 真实用户 MVP 应与 HF Demo 分开：前者优先手动字段、受控采购上下文、规则审核、导出和人工复核。
- README 需要三条清晰入口：面试官 3 分钟看懂、开发者 10 分钟跑起、试用者先看到数据和责任边界。

## 9. 分阶段路线图

| 阶段 | 目标 | 不做什么 | 文件类型 | 验收标准 | 主要风险 | 阻塞真实用户试用 | 阻塞开源发布 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 4A | 完成产品化/开源差距审计和优先级排序 | 不改业务链、不接模型、不改 HF/Docker | docs、reports、状态文档 | 审计覆盖七维度；JSON 可解析；路线图可执行 | 把 Demo 能力误判为产品能力 | 是，作为决策前置 | 是，作为发布前置 |
| Phase 4B | 干净 clone Quickstart、repo hygiene、许可与边界说明 | 不新增产品功能、不接 live inference | README、`.env.example`、LICENSE、sample、测试脚本、docs | 新环境按一页 Quickstart 启动 API/Demo；sample audit 成功；分层测试可运行 | 依赖安装差异、数据许可表述不完整 | 否，但明显降低试用门槛 | 是 |
| Phase 4C | 用户可手动录入发票字段和 mock PO/GRN，运行真实 Phase 2 主链 | 不把附件上传包装成模型抽取；不做 ERP/认证/多租户 | API schema、service、轻量 UI、sample data、tests | 用户无需改代码完成一次审核；字段来源清楚；规则结果稳定 | 输入契约与现有 mock 数据耦合 | 是 | 否 |
| Phase 4D | AuditReport 导出与人工审核 UX 闭环 | 不做付款执行、不让 LLM 改规则结论 | export service、review UI/API、audit docs、tests | JSON/Markdown 可下载；备注/决策/trace 可追溯；fallback 状态可见 | 审核状态并发和隐私泄露 | 是，若试用目标包含完整闭环 | 否 |
| Phase 4E | 可选 Docker/部署加固 | 不重构核心业务、不承诺企业级高可用 | Docker、Compose、CI、deployment docs | 干净构建；健康检查；持久卷；非 root；reset/upgrade 说明；runtime smoke | 当前环境缺 Docker CLI、平台差异 | 否 | 否，若先明确未验证边界 |
| Phase 4F | 可选在线 OCR/LayoutLMv3 推理 | 不接在线 LoRA；不让模型决定风险/动作 | inference adapter、model manifest、upload validation、observability、tests | 受控图片可推理；置信度/失败/人工纠正可见；资源指标有记录 | 权重许可、成本、延迟、泛化、安全文件处理 | 否，手动输入 MVP 可先试用 | 否 |

## 10. 推荐顺序

直接进入 **Phase 4B**，不需要先补新的审计阶段。Phase 4B 完成后进入 4C，再进入 4D。4E 和 4F 均为可选加固，不应阻塞手动输入版真实用户 MVP。

## 11. 本轮验证边界

- 已检查所有指定输入文档存在。
- 已读取 Phase 3J/3K Markdown 与 JSON 的边界和核心指标。
- 已检查 README、FastAPI 路由、Pydantic 模型、配置、CI、Docker 和 `.gitignore`。
- 本轮只改文档和报告，不运行全量测试；全量测试不能为审计文档提供额外有效信号，且工作区已有其他线程的未提交 Phase 3 变更。
