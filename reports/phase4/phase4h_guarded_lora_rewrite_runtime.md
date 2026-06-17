# Phase 4H：Guarded LoRA Rewrite Runtime Report

## Status

Phase 4H completed.

The runtime now supports:

- `template`
- `guarded_lora`
- `shadow_lora`

Legacy `shadow` and `experimental` modes remain compatible.

## What Changed

- Added product-mode explanation semantics to the fallback orchestrator.
- Added provider metadata and local unavailable-provider stub.
- Extended Guard result with structured violation details.
- Extended AuditReport explanation metadata with mode/source/hash/provider/guard trace.
- Connected `guarded_lora` into `/api/mvp/audit/execute`.
- Added Phase 4H regression tests with fake providers only.

## Phase 3E / 3G Failure Context

Phase 3E showed low format compliance and hallucinated unknown amounts, GRNs and supplier relationships.

Phase 3G still failed hard gates:

- format compliance: `0.0000`
- factual consistency: `0.9000`, below `0.9500`
- action consistency: `0.4500`, below `0.9000`
- anomaly coverage: `0.4250`, below `0.9000`
- hallucination rate: `0.1500`, above `0.0500`

Therefore Phase 4H does not promote LoRA to a reliable explanation model. It only implements a guarded runtime.

## Runtime Contract

```text
Phase 2 deterministic audit
-> Canonical Audit Facts
-> Deterministic Template
-> LoRA rewrite candidate
-> Guard
-> PASS: LoRA explanation
-> FAIL: template fallback
```

`risk_level`, `recommended_action`, `anomaly_types`, validation evidence and confirmed fields remain read-only upstream facts.

## Provider Status

Real LoRA adapter runtime is not wired in this repository.

Clean clone behavior:

- `template` works without model weights.
- `guarded_lora` without provider falls back to template with `provider_unavailable`.
- fake providers are used only for tests and do not claim model quality.

## Guard Coverage

The Guard rejects:

- changed risk level
- changed recommended action
- added or missing anomaly types
- unknown invoice / PO / GRN identifiers
- unknown amount
- unknown vendor
- unknown date
- unsupported policy section or approver role
- missing field completion
- forbidden payment or audit-bypass claims
- missing required template sections

## 4G-EXT Integration

`POST /api/mvp/audit/execute` accepts `explanation_mode=guarded_lora`.

When no provider is configured, the API still returns AuditReport JSON, Markdown and trace. The trace records fallback, while Phase 2 risk/action remain deterministic.

## Validation Summary

- Phase 4H runtime tests passed.
- Phase 3H explanation tests passed.
- Phase 4G-EXT and API regression tests passed.
- Broader Phase 3 explanation tests passed.
- `pip check`, JSON parse, markdown link check and `git diff --check` passed.

Full test suite was not run because this phase is explanation-runtime scoped and several full-suite paths include heavier demo/release checks outside the edited surface.

## Remaining Risks

- No real LoRA adapter runtime is available.
- Guard is conservative and may reject safe paraphrases.
- Raw LoRA output is suitable for local trace only; production logging needs stricter privacy controls.
- High-risk audit explanations remain template-only by default.
