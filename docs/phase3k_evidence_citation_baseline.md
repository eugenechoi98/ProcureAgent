# Phase 3K Evidence Citation Baseline

## 目标与边界

Phase 3K 在 Phase 3J 结构化输出之后增加离线引用约束：

```text
Canonical Audit Facts
-> Evidence Catalog
-> CitationStructuredExplanation
-> Claim-Evidence Validator
-> Citation Renderer
-> Template Fallback
```

本轮不训练、不加载模型、不访问网络、不接 API，也不修改 Phase 1、Phase 2、Demo 或 Docker。deterministic template 继续作为正式默认解释，citation-grounded explanation 仅用于离线验证。

## Evidence Catalog

Evidence Catalog 只从 `CanonicalAuditFacts` 构造，包含稳定 ID、枚举来源、字段、规范值、允许 claim type 和展示文本。模型输出不能写回目录。

来源类型限定为：invoice、po、grn、duplicate_check、policy、risk_rule、audit_fact。

## 校验规则

- 每条 bullet 必须有 evidence ID 和 claim type。
- ID 必须存在，claim type 必须被绑定证据允许。
- PO、GRN、发票号、金额、供应商、政策、风险和动作必须由当前 bullet 的证据支持。
- 所有上游异常必须有 anomaly citation。
- 任一失败都返回现有 deterministic template，fallback 文本不带 citation-grounded 标记。

## Challenge 与指标

固定 challenge set 有 20 条 synthetic fixtures，不是训练数据。Evaluator 分开报告 accepted-only 和 all-candidate 指标，避免把故意构造的非法候选与已接受输出混在一起解释。

运行：

```powershell
.\.venv\Scripts\python.exe scripts\phase3\run_evidence_citation_baseline.py
.\.venv\Scripts\python.exe -m pytest tests\test_phase3k_evidence_citation.py -q
```

## 已知限制

Evidence citation 只证明“声明绑定了可追溯证据并通过当前规则”，不等于通用语义蕴含，也不能宣称彻底解决 hallucination。未来即使接入模型，也必须复用同一 validator、Guard 和 fallback。
