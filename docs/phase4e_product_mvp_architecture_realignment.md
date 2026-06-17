# Phase 4E-R: Product MVP Architecture Realignment

## 结论

ProcureGuard AI 的当前目标是**开源可运行、真实用户可体验的受控采购发票审核 MVP**。它不应停留在离线 artifact 展示，也不应在核心用户链路尚未验证前扩张为企业级生产系统。

目标链路为：

```text
Invoice Image
-> OCR tokens + bbox
-> LayoutLMv3 field extraction
-> ExtractedFields candidates
-> Human confirmation/correction
-> Phase 2 deterministic audit / three-way match / Policy RAG / Risk Engine
-> AuditReport
-> Deterministic template explanation
-> optional LoRA controlled rewrite candidate
-> Guard
-> PASS: enhanced explanation
-> FAIL: deterministic template fallback
```

## 目标与边界

### 当前开源 MVP 是什么

- 开发者可以 clean clone，并运行手动字段审核、AuditReport 导出和人工复核流程。
- 后续用户可以在本地提交发票图片，获得 OCR 与 LayoutLMv3 字段候选，确认后进入真实 Phase 2 确定性审核链。
- 每个结果明确标记输入来源、模型使用状态、mock context、fallback 和付款权限。
- `risk_level`、`recommended_action` 和 `anomaly_types` 只由确定性规则生成。
- AuditReport 是研究型审核结果，不是付款凭证或企业合规批准。

### 为什么不能只展示离线证据

Phase 1 的真实 checkpoint 推理和 Phase 3 的失败治理证据可以证明实验做过，但不能证明陌生用户能够把自己的输入送入抽取、确认、审核和导出链路。产品 MVP 必须把已有能力连接成可操作流程，同时保留离线指标的真实边界。

### 为什么不直接做企业级生产系统

认证、多租户、ERP、SLA、付款执行和完整数据治理会显著扩大范围，却不能替代对图片抽取质量、字段确认体验和规则审核价值的验证。当前先证明本地单用户闭环，再根据真实试用反馈决定持久化与部署投入。

## 核心架构决策

### LayoutLMv3 live extraction

Phase 4F 先做本地 spike，不立即修改 HF public Demo：

1. 校验图片格式、大小和页数。
2. OCR adapter 生成 words、normalized bbox 和置信度。
3. 本地加载受支持的 LayoutLMv3 checkpoint，输出字段 span、值、置信度和来源。
4. 通过稳定 adapter 转成 `ExtractedFields` 候选，不直接进入风险判断。
5. 记录延迟、内存、CPU/GPU 行为、缺失权重和推理失败状态。

只有 checkpoint 分发边界、资源需求、错误契约和样例质量可复现后，才进入用户输入主链。

### OCR 的角色

OCR 是 LayoutLMv3 的输入来源，负责提供 token、bbox 和可选置信度；它不是字段抽取模型的替代品。OCR 文本可用于可视化、人工修正和 fallback 诊断，但不能被包装为 LayoutLMv3 预测。

### 字段确认门

字段候选需要人工确认或修正后再进入 Phase 2。界面或 API 至少应展示原值、置信度、页面/bbox 来源和修正值；低置信度、缺失字段和格式异常必须显式提示。这个门避免抽取错误被误当作采购异常。

### Phase 2 决策核心

确认后的 `ExtractedFields` 继续调用现有三单匹配、重复检测、正式自研 Policy RAG、Risk Engine 和 AuditReport。模型不得写回规则事实，也不得覆盖 `risk_level`、`recommended_action` 或 `anomaly_types`。

### LoRA controlled rewrite

LoRA 只在 AuditReport 和 Canonical Audit Facts 已冻结后生成语言增强候选。默认仍返回 deterministic template；实验模式必须显式启用，并保留原始模板、候选输出、模型版本与 guard 结果。

Guard 上线条件：

- 输出可解析且满足固定 schema/章节要求。
- 风险、动作、异常、缺失字段与 Canonical Audit Facts 完全一致。
- 金额、供应商、PO/GRN、政策和 evidence ID 不得新增或篡改。
- 空输出、超时、模型不可用、未知事实或任何校验失败均 fail closed。
- Guard FAIL 必须返回 deterministic template，并记录 fallback reason。
- 在真实模型候选通过离线 hard gate 和回归集前，不作为默认用户输出。

### LangChain comparison

LangChain Policy RAG comparison 放在 Phase 4I。它只作为相同本地政策语料、相同查询与指标下的 optional integration benchmark；现有 SQLite FTS5/BM25 自研 Policy RAG 继续是正式主链。

## 后置能力

| 能力 | 推荐时机 | 判断条件 |
|---|---|---|
| SQLite persistence / local workspace | Phase 4G 后评估，必要时纳入 4J | 多步骤试用确实需要跨重启保存和恢复 |
| Attachment upload mode | Phase 4F/4G | 图片校验、临时文件清理和抽取错误契约完成 |
| Docker hardening | Phase 4J | 本地链路稳定、依赖与模型资产边界明确 |
| HF live inference | 4F/4G 本地门槛通过后单独评估 | CPU/GPU、冷启动、模型分发、隐私和成本可接受 |
| auth / multi-tenant | 开源 MVP 获得真实采用后 | 明确用户、数据隔离和运维需求 |
| ERP / payment execution | 不在当前 Phase 4 路线 | 需要独立安全、合规和企业集成项目 |

## 推荐路线

### Phase 4E：Product MVP Architecture Realignment

目标：冻结产品 MVP 的输入、抽取、确认、审核和受控解释边界。本轮只更新路线与架构文档，不实现 live inference。

验收：项目状态文件和报告采用同一目标定义；SQLite 不再是当前第一优先级。

### Phase 4F：Local Live OCR / LayoutLMv3 Extraction Spike

目标：用少量可复核图片跑通本地 OCR token+bbox、checkpoint 推理和字段候选输出。

不做：不接 HF live inference，不把单样本结果写成泛化指标，不进入风险决策。

验收：固定命令可复现；输出含字段值、置信度、来源和失败状态；记录资源与延迟。

### Phase 4G：Field Confirmation + Phase 2 Audit Integration

目标：增加字段确认/修正门，并把确认结果接入现有 deterministic audit 与 AuditReport。

不做：不让抽取模型直接决定风险，不接 ERP 或付款。

验收：用户可从图片走到可导出的 AuditReport；抽取值与修正值均可追溯。

### Phase 4H：Guarded Explanation Runtime Integration

目标：在默认模板之外提供显式实验模式的 LoRA controlled rewrite、Guard 和 fallback。

不做：不改变风险、动作、异常类型，不以未过 hard gate 的模型替换默认模板。

验收：PASS/FAIL 可审计；所有失败稳定回退；默认模式无模型依赖。

### Phase 4I：LangChain Policy RAG Comparison

目标：在正式 Policy RAG 主链不变的前提下完成可复现 comparison。

不做：不以框架替换自研检索，不改变风险结果。

验收：同语料、同查询、同指标，差异和限制有报告。

### Phase 4J：Open-source Release Readiness

目标：验证 clean clone、模型资产说明、sample、隐私边界、文档链接和可选部署路径。

不做：不宣称企业生产就绪，不默认要求 Docker 或在线模型。

验收：陌生开发者可按 Quickstart 跑通核心 MVP；live/offline/mock 边界清晰；必要时再加入最小 workspace/persistence。

## 已有证据入口

- [Phase 4A 产品化差距审计](phase4a_productization_gap_audit.md)
- [Open-source Quickstart](OPEN_SOURCE_QUICKSTART.md)
- [Phase 4C 手动输入流](phase4c_user_facing_mvp_input_flow.md)
- [Phase 4D 导出与人工复核](phase4d_audit_report_export_review_ux.md)
- [项目架构](../ARCHITECTURE.md)
