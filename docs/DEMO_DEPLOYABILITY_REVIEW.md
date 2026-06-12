# Demo Deployability Review

## Review Scope

This review evaluates local and future public demo options. It does not create
or deploy a Hugging Face Space, load a model, download a checkpoint, start a
GPU, or validate online resource limits.

Local readiness in this phase means only that repository fixtures and the
deterministic demo path can be checked offline. It is not an online deployment
approval.

## Current Demonstrable Flow

```text
Invoice Input
-> Phase 2 Deterministic Audit
-> Canonical Audit Facts
-> Deterministic Template Explanation
-> Optional Guarded Rewrite
-> Safe Fallback
-> Explanation Audit Trail
-> AuditReport
```

The default path:

- does not require a model;
- does not require a GPU;
- does not require an API key;
- does not require network access;
- does not run a real LoRA adapter;
- does not depend on a third training run.

The repository already contains 13 fixed Phase 3H demo cases and tests for
template, shadow, experimental, high-risk, guard-failure, and provider-failure
paths.

## Demo Mode Assessment

### Mode A: Fixed Cases

```text
Fixed invoice or fixed extracted result
-> fixed audit path
-> fixed display result
```

| Item | Assessment |
| --- | --- |
| Stability | High for the current deterministic fixtures |
| Startup speed | Fast in local tests; deployment cold-start time is pending measurement |
| Memory | Uses the lightweight API/test dependency path; deployed peak memory is pending measurement |
| Model required | No |
| Interview suitability | High as a reliable scripted walkthrough |
| Fallback suitability | High |
| Main limitation | Demonstrates known scenarios rather than arbitrary documents |

Mode A is the safest fallback because it is fully offline and reproducible.

### Mode B: Hybrid

```text
Fixed or pre-generated ExtractedFields
-> live Phase 2
-> live Canonical Facts
-> live template explanation
-> live Audit Trail
```

| Item | Assessment |
| --- | --- |
| Stability | High in the current automated tests |
| Startup speed | Fast in local tests; hosted cold-start time is pending measurement |
| LayoutLMv3 dependency | No |
| LoRA dependency | No |
| Real rule-chain visibility | Yes, it runs matching, duplicate, policy, risk, facts, template, and audit output |
| Default public demo suitability | Recommended |
| Main limitation | Document extraction is represented by fixed or pre-generated fields |

Mode B presents more real engineering behavior than fixed result playback while
keeping the model and checkpoint risks outside the first deployment.

### Mode C: Full Online Extraction

```text
Uploaded image
-> online LayoutLMv3
-> Phase 2
-> explanation layer
```

| Item | Assessment |
| --- | --- |
| Fine-tuned checkpoint size | Not locally verifiable in the current workspace |
| Checkpoint hosting | A Hugging Face Model Repository is preferable to Git history; exact setup is pending review |
| CPU inference | Latency and compatibility risk; pending measurement |
| GPU requirement | Pending measurement |
| Peak memory | Pending measurement |
| Cold start | Pending measurement |
| Model download latency | Pending measurement |
| Network dependency | Yes if weights are downloaded during build or startup |
| Free Spaces resources | Availability and sufficiency are pending measurement |
| Default public demo suitability | Not recommended for the first deployment |

The local Hugging Face cache contains the public
`microsoft/layoutlmv3-base/model.safetensors`, but this is not the fine-tuned
Phase 1 checkpoint. Therefore it is not evidence that the completed extraction
path can be deployed online from this repository.

## Recommendation

Recommended initial public demo:

1. **Default: Mode B hybrid.** Use fixed or pre-generated `ExtractedFields`,
   then run the live Phase 2 rules, Canonical Facts, deterministic template,
   and explanation audit metadata.
2. **Fallback: Mode A fixed cases.** Keep the 13 deterministic fixtures
   available when file upload or runtime state is unsuitable.
3. **Optional later enhancement: Mode C.** Evaluate online LayoutLMv3 only
   after the fine-tuned checkpoint is available and CPU/GPU, memory, latency,
   cold-start, and download behavior are measured.
4. **Real LoRA remains disabled.** It failed the documented hard gates and is
   not needed by the recommended demo.

This recommendation does not require an API key, GPU, or model upload for the
first demo.

## Model Asset Inventory

### Git Repository

The tracked repository contains no `.safetensors`, `.bin`, `.pt`, or `.pth`
model weights. `.gitignore` excludes checkpoints, artifacts, and safetensors.

| Asset | Tracked in Git | Verified size | Current use |
| --- | --- | ---: | --- |
| Fine-tuned LayoutLMv3 checkpoint | No | Not available for verification | Offline Phase 1 result evidence only |
| Qwen base model | No | Not tracked | Not used by default demo |
| LoRA adapter | No | Not tracked | Disabled |

### Locally Verifiable, Untracked Assets

| Asset | Location | File | Size |
| --- | --- | --- | ---: |
| Public LayoutLMv3 base cache | repository-local ignored cache | `model.safetensors` | 501,338,056 bytes |
| Qwen2.5-0.5B-Instruct base | `D:\ProcureAgent_LocalArtifacts\Phase3\Qwen2.5-0.5B-Instruct` | `model.safetensors` | 988,097,824 bytes |
| First-run LoRA adapter | `D:\ProcureAgent_LocalArtifacts\Phase3\phase3_first_lora_run\phase3\adapters\qwen2.5-0.5b-anomaly-explainer` | `adapter_model.safetensors` | 35,237,104 bytes |

Important limits:

- the 501,338,056-byte file is the public LayoutLMv3 base model, not the
  fine-tuned Phase 1 checkpoint;
- the Phase 1 fine-tuned checkpoint is not present in the checked workspace or
  known local artifact directory;
- the second-run LoRA artifact copy is not present locally, as already recorded
  in the Phase 3G review;
- no current recommended demo mode needs any of these model files.

### Hosting Assessment

- Model weights should not be committed to ordinary Git history.
- Git LFS is technically intended for large files, but a Hugging Face Model
  Repository is the clearer future option for versioned model distribution.
- Downloading weights during Space build or startup adds network and cold-start
  risk and must be measured before selecting that approach.
- No model needs to be uploaded for the recommended hybrid or fixed-case demo.

## Spaces Resource Assessment

| Area | Assessment |
| --- | --- |
| Python | Project metadata requires Python `>=3.10`; exact hosted version should be pinned only after local compatibility testing |
| UI framework | Gradio is recommended for a future interview demo UI; the existing FastAPI service can remain the domain backend |
| CPU-capable path | Fixed cases, Phase 2 rules, Canonical Facts, deterministic template, and audit metadata |
| Potential GPU path | Online LayoutLMv3 or real LoRA, both outside the first demo |
| Memory risk | Low for fixed/hybrid relative to model paths; hosted peak values are pending measurement |
| Cold-start risk | Low for fixed/hybrid relative to model paths; actual hosted time is pending measurement |
| Download risk | None for fixed/hybrid; significant and pending measurement for model modes |
| Network risk | None for a packaged fixed/hybrid demo; model downloads would add network dependency |
| Secrets/API key | Not required for fixed or hybrid mode |
| Fixed fallback | Required for a reliable public demo |

No Space is created in this phase, and no formal Space configuration or
metadata is added.

## Local Readiness Check

Run:

```powershell
.\.venv\Scripts\python.exe scripts\demo\verify_demo_readiness.py
```

The command validates the 13 fixed cases, required modes, fixed risk/action,
anomaly lists, explanation source, fallback expectations, and offline
requirements. It prints JSON and writes no file by default. Use `--output` only
when a saved local report is explicitly needed.

This check does not start FastAPI, load a checkpoint, inspect GPU capability,
or prove that a Hugging Face Space will deploy successfully.

## Suggested Future Batches

1. **Spaces 0: static and hybrid design freeze.** Define screens, fixture
   selection, and output presentation.
2. **Spaces 1: minimal Gradio demo, local only.** Run the hybrid flow locally
   without model downloads.
3. **Spaces 2: fixed-case fallback.** Add a clear deterministic fallback path.
4. **Spaces 3: Hugging Face Spaces deployment.** Deploy only after local
   behavior and resource configuration are verified.
5. **Spaces 4: optional online LayoutLMv3 evaluation.** Measure checkpoint
   delivery, CPU/GPU latency, memory, and cold start before deciding whether to
   expose it.

Real LoRA integration and LangChain comparison remain outside these batches
unless separately approved.
