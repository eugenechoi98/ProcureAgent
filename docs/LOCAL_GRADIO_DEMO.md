# Local Gradio Demo

## Scope

This is a local offline interview demo. It is not a Hugging Face Space and is
not an online deployment result.

The demo does not:

- load LayoutLMv3;
- load Qwen;
- load a real LoRA adapter;
- use a GPU;
- call a network API;
- require an API key;
- change Phase 2 rules or database schema.

## Install

Install the normal project dependencies in the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Gradio 5.x is the only new UI dependency. Phase 3 GPU requirements are not
changed.

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

Both commands print JSON and write no file unless `--output <path>` is
explicitly provided.

## Current Limits

- Online LayoutLMv3 extraction is disabled.
- Real LoRA is disabled.
- Static fallback is required for cases that Phase 2 cannot reproduce exactly
  without changing sealed business logic.
- The structured guard is not a production semantic verifier.
- No Hugging Face Space has been created.
