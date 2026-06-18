# Phase 4H：Guarded LoRA Rewrite Runtime

## 结论

Phase 4H 将解释层收口为产品级运行时：

```text
Canonical Audit Facts
-> Deterministic Template
-> Optional LoRA Rewrite Candidate
-> Strict Guard
-> PASS: LoRA enhanced explanation
-> FAIL: Template fallback
```

本轮没有重新训练 LoRA，也没有证明 LoRA 已经可靠。Phase 3E 和 Phase 3G 的真实评测都未通过 hard gate，因此 LoRA 仍只能作为受控语言改写候选。

## 运行模式

- `template`：只使用 deterministic template，不调用 provider。
- `guarded_lora`：生成模板后调用 provider，Guard PASS 才使用 LoRA rewrite；provider 不可用、输出为空、解析失败、Guard FAIL 或高风险场景都 fallback template。
- `shadow_lora`：尝试 provider 和 Guard，但最终始终返回 template，只记录候选和 Guard 结果。

旧模式 `shadow` 与 `experimental` 保持兼容；新 API 推荐使用 `shadow_lora` 和 `guarded_lora`。

## 硬边界

LoRA 永远不能修改：

- `risk_level`
- `recommended_action`
- `anomaly_types`
- confirmed/extracted fields
- validation result
- PO、GRN、invoice number、vendor、amount、date、policy evidence
- Phase 2 deterministic audit 结果
- field confirmation 或 review decision

风险等级和建议动作已经在解释层之前由 Phase 2 deterministic rules 生成。解释层只能改变最终解释文本来源，不能回写审核结构化结论。

## Provider Status

当前 clean clone 默认不加载真实 LoRA adapter。代码提供 provider interface、`UnavailableLoRARewriteProvider` 和可显式开启的 `LocalLoRARewriteProvider`，但不会伪造真实 LoRA 成功。

测试中的 fake provider 只用于验证 Guard 行为和 fallback，不代表模型质量。

Provider 输入只能包含：

- deterministic template explanation
- Canonical Audit Facts

Provider 不允许接收 raw OCR、raw LayoutLMv3 candidates、unconfirmed fields 或 Phase 2 之外的临时事实。

## Local LoRA Runtime

真实 LoRA rewrite provider 必须显式开启：

```powershell
$env:PROCUREGUARD_LORA_ENABLED="1"
$env:PHASE3_MODEL_DIR="D:\ProcureAgent_LocalArtifacts\Phase3\Qwen2.5-0.5B-Instruct"
$env:PROCUREGUARD_LORA_ADAPTER_DIR="D:\ProcureAgent_LocalArtifacts\Phase3\phase3_first_lora_run\phase3\adapters\qwen2.5-0.5b-anomaly-explainer"
$env:PROCUREGUARD_LORA_DEVICE="auto"
$env:PROCUREGUARD_LORA_MAX_NEW_TOKENS="256"
$env:PROCUREGUARD_LORA_SUBPROCESS="1"
.\.venv\Scripts\python.exe -m uvicorn procureguard.api.main:app --host 127.0.0.1 --port 8000
```

开启后，`create_app()` 会从环境变量构造 `LocalLoRARewriteProvider`。如果 base model、tokenizer、adapter config 或 adapter weights 缺失，API 会在启动时 fail fast，不会回退成“假 LoRA 成功”。`PROCUREGUARD_LORA_SUBPROCESS=1` 会把 Qwen/LoRA 推理隔离到子进程，避免与 OCR/LayoutLMv3 运行时互相污染。

当前 Windows `.venv` 已补齐 `peft==0.13.2` 和 `accelerate==1.1.1`。仓库仍不提交 Qwen base model 或 adapter 权重；本机真实资产位于 `D:\ProcureAgent_LocalArtifacts\Phase3`。

## Guard Coverage

Guard fail closed，覆盖：

- risk level 变化
- recommended action 变化
- anomaly type 新增或遗漏
- 未知 invoice / PO / GRN
- 未知 amount
- 未知 vendor
- 未知 date
- 未知 policy section 或 approver role
- missing fields 被补全
- 付款执行或绕过审核等 forbidden claim
- 必需章节缺失

Guard 输出包含 `guard_passed`、`violations`、结构化 violation details、checked entities、checked numbers 和 checked decision fields。

## Audit Trace

`AuditReport.explanation` 记录：

- requested / used explanation mode
- final source：`template | lora | fallback`
- template version、guard version、prompt version
- provider、model、adapter、latency
- facts hash、template hash、LoRA candidate hash
- guard result、violations、fallback reason
- raw LoRA output 是否仅保存到本地 trace

## 4G-EXT 接入

`POST /api/mvp/audit/execute` 已支持 `explanation_mode=guarded_lora`。默认无 provider 时仍可完成：

```text
confirmed_fields
-> Phase 2 deterministic audit
-> template explanation fallback
-> JSON / Markdown / trace
```

trace 会记录 `provider_unavailable`。Guard PASS/FAIL 都不会改变 `risk_level`、`recommended_action` 或 evidence。

## 当前风险

- 真实 LoRA adapter 未接入，当前只完成运行时安全门。
- Guard 是规则型 exact/regex 校验，不等同于完整语义蕴含验证。
- 高风险场景默认 template only，避免在高风险发票上引入语言模型不确定性。
- raw LoRA output 只适合本地 trace；真实用户数据场景仍需要更严格隐私和日志治理。
