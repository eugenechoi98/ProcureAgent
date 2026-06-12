# Local Gradio Demo

## Scope

This is a local offline interview demo. It is not a Hugging Face Space and is
not an online deployment result.

It is now the local **Unified Portfolio Demo** with three tabs:

```text
Tab 1: Invoice Audit
Tab 2: Model Lab
Tab 3: Architecture
```

Invoice Audit keeps the frozen stable business flow. Model Lab reads only the
lightweight offline artifacts in `demo/model_lab/`. Architecture explains the
model, Agent, rules, Guard, Fallback, and Audit Trail boundaries.

The demo does not:

- load LayoutLMv3;
- load Qwen;
- load a real LoRA adapter;
- use a GPU;
- call a network API;
- require an API key;
- change Phase 2 rules or database schema.

## Install

Install the normal FastAPI backend dependencies in the project virtual
environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

This default installation does not install or require Gradio.

Install the local Demo dependency explicitly:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[demo]"
```

Gradio is a Demo-only optional dependency pinned to the verified
`gradio==5.50.0`. Phase 3 GPU requirements are not changed. Without this
optional dependency, the core backend remains importable and only the Demo
entry point reports the `.[demo]` installation command.

## Start

```powershell
.\.venv\Scripts\python.exe -m demo.app
```

The app binds to:

```text
http://127.0.0.1:7860
```

It uses `share=False`, does not create a public link, and does not open an
external browser automatically.

This remains a local offline Demo. It does not create a Hugging Face Space,
require an API key or GPU, or load Qwen or a real LoRA adapter.

## Default Hybrid Path

The default selection is:

```text
normal_invoice + template
```

It runs:

```text
pre-generated ExtractedFields
-> in-memory Phase 2 deterministic audit
-> Canonical Audit Facts
-> deterministic template
-> explanation metadata
-> AuditReport
```

This path is marked `LIVE HYBRID AUDIT` in the page.

The current sealed Phase 2 fixtures cannot precisely recreate every one of the
13 canonical demo facts. Those cases use the already-reviewed static fixture
through the same renderer, guard, and orchestrator. The page marks them
`STATIC FALLBACK`, includes `hybrid_execution_unavailable`, and displays a safe
error summary. They are not presented as successful live audits.

## Explanation Modes

| UI mode | Orchestrator behavior |
| --- | --- |
| `template` | Default deterministic template; no provider call |
| `shadow` | Fake valid rewrite is guarded and recorded, but template remains official |
| `experimental_guard_pass` | Fake valid rewrite is used after guard PASS |
| `experimental_guard_fail` | Fake rewrite adds an unknown invoice number and falls back |
| `provider_runtime_error` | Fake provider raises and falls back with `model_runtime_error` |
| `invalid_output` | Fake provider returns an integer and falls back with `invalid_lora_output` |

High-risk facts always return the deterministic template.

All providers are local test doubles. No real model inference is configured.

## Page Fields

Inputs:

- Demo Case;
- Explanation Mode;
- Run Audit;
- Reset.

Outputs:

- execution path and fallback status;
- Case ID and Invoice ID;
- Risk Level and Recommended Action;
- Anomaly Types, Evidence, and Missing Fields;
- Explanation Text and Explanation Source;
- Used Rewrite, Guard Passed, and Fallback Reason;
- Facts Hash;
- Template, Prompt, Model, and Adapter versions;
- Raw Rewrite Output;
- Safe Fallback Detail;
- complete AuditReport JSON.

## Offline Checks

Readiness:

```powershell
.\.venv\Scripts\python.exe scripts\demo\verify_demo_readiness.py
```

Service smoke:

```powershell
.\.venv\Scripts\python.exe scripts\demo\run_local_demo_smoke.py
```

Unified Portfolio Demo smoke:

```powershell
.\.venv\Scripts\python.exe scripts\demo\run_unified_portfolio_demo_smoke.py
```

Both commands print JSON and write no file unless `--output <path>` is
explicitly provided.

## Current Limits

- Online LayoutLMv3 extraction is disabled.
- Real LoRA is disabled.
- Static fallback is required for cases that Phase 2 cannot reproduce exactly
  without changing sealed business logic.
- The structured guard is not a production semantic verifier.
- No Hugging Face Space has been created.
- Current web UI does not run live LayoutLMv3 inference.
- Current web UI does not run real LoRA inference.

## Role In The Unified Portfolio Demo

The local Gradio presentation now has:

```text
Tab 1: Invoice Audit   -> completed local baseline
Tab 2: Model Lab       -> reads real offline lightweight artifacts
Tab 3: Architecture    -> explains deterministic governance boundaries
```

Model Lab uses real offline LayoutLMv3 and LoRA artifacts rather than loading
heavy models in the web process. Architecture explains why risk and action stay
deterministic and why guarded rewrite cannot change audit facts.

The Invoice Audit baseline remains valuable for reliable live behavior, while
the new tabs make PyTorch, Transformers, LoRA/QLoRA, Agent, and RAG work
visible. Hugging Face Spaces deployment, online LayoutLMv3, real LoRA
inference, LangChain comparison, Docker, and CI are later batches and are not
completed by this local Demo.
