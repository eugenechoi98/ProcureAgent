# Portfolio Demo Design

## Status

This document freezes the presentation architecture for the ProcureGuard AI
portfolio Demo and records the current local implementation status. It does not
change the auditing business chain, deploy a Hugging Face Space, or enable live
model inference.

Engineering Closure has completed the Unified Demo, offline Model Lab artifacts,
offline LangChain compatibility benchmark, Docker Compose configuration, GitHub
Actions CI, and Release Readiness. The CPU-only public Space is available at
https://huggingface.co/spaces/eugene-98/procureguard-ai-demo. HTTP, configuration,
and Gradio API checks passed; a manual visual browser check remains required.
SQLite FTS5 / BM25 remains the official Policy RAG chain.

## 1. Current Problem

The completed local Gradio Demo is a necessary foundation:

- stable business workflow;
- no GPU;
- no API key;
- no model download;
- visible Guard, Fallback, and Audit Trail behavior.

It is not the final portfolio destination by itself:

- the real LayoutLMv3 results are not visible in the UI;
- the two real LoRA training runs are not visible in the UI;
- most canonical cases currently use clearly labeled `STATIC FALLBACK`;
- a visitor may incorrectly conclude that the project is only a rule system.

The stable Demo will be retained as the business baseline. The portfolio layer
will add model evidence and architecture explanation without weakening runtime
reliability or changing sealed Phase 2 decisions.

## 2. Unified Gradio App

The final Portfolio Demo is one Gradio App with three tabs:

```text
Tab 1: Invoice Audit
Tab 2: Model Lab
Tab 3: Architecture
```

### 2.1 Tab 1: Invoice Audit

Displayed live flow:

```text
Pre-generated ExtractedFields
-> live Phase 2
-> Policy RAG
-> Risk Engine
-> Canonical Audit Facts
-> Template / Guard / Fallback
-> AuditReport
```

Goals:

- preserve the current stable, CPU-only baseline;
- evaluate whether 3 to 4 representative cases can run through the live chain;
- never modify Phase 2 risk rules to make a Demo case convenient;
- keep unsupported cases explicitly labeled `STATIC FALLBACK`.

Priority cases:

```text
normal_invoice
missing_po_number
duplicate_invoice
amount_discrepancy
```

`normal_invoice` already runs the live hybrid chain. The other cases require a
separate feasibility review against existing Phase 2 fixtures. A case remains
static when exact reproduction would require changing sealed business logic.

### 2.2 Tab 2: Model Lab

Model Lab has two sections.

#### LayoutLMv3 Extraction Lab

Required metrics:

```text
OCR + Regex baseline macro F1 = 0.4387
Corrected LayoutLMv3 macro F1 = 0.8067
Date F1 = 0.1423 -> 0.8764
```

Required evidence:

- real offline metrics and evaluation split label;
- training loss curve;
- 3 to 5 real prediction cases;
- field-level ground truth and prediction;
- error attribution;
- artifact source, run, and limitation notes.

The results must retain the existing labels
`offline_checkpoint_inference`, `local_validation_split_seed_42`, and
`official_test=false`.

#### LoRA Explanation Lab

Required evidence:

- training parameters for both real runs;
- training and validation loss for both runs;
- base and fine-tuned metrics;
- hallucination examples;
- Guard rejection reasons;
- deterministic template fallback;
- Phase 3F fact-constrained prompt and gold-answer design.

The UI must display:

```text
ModelScope real offline experiment result
Not current web real-time inference
```

The second adapter failed the deployment hard gates. Model Lab presents this as
an engineering result and governance decision, not as a production model
success.

### 2.3 Tab 3: Architecture

The minimum system diagram is:

```text
Invoice
-> LayoutLMv3
-> Agent Tools
-> Three-Way Match
-> Policy RAG
-> Risk Engine
-> Canonical Facts
-> Template / Controlled Rewrite
-> Guard
-> Fallback
-> Audit Trail
```

The tab must explain:

- a model cannot directly decide risk because financial decisions require
  reproducible rules and evidence;
- LoRA cannot change `recommended_action`, `risk_level`, anomaly types,
  evidence, or missing fields;
- a third training run is paused because the second adapter failed every
  deployment hard gate;
- the deterministic template remains valuable because it is reproducible,
  auditable, and available without a model.

## 3. Runtime And Artifact Boundaries

### Default Live Runtime

```text
Phase 2 audit chain
Policy RAG
Risk Engine
Canonical Audit Facts
Deterministic Template
Guard / Fallback demonstration
AuditReport
```

### Real Offline Artifacts

```text
LayoutLMv3 training and checkpoint inference evidence
Two real LoRA runs, metrics, losses, and hallucination cases
```

Offline evidence must include its source and evaluation scope. It must not be
described as live inference.

### Optional Later Work

```text
Online LayoutLMv3
Online real LoRA
GPU Space
Phase 3I
```

These items are not implemented and are not blockers for the first portfolio
release.

## 4. Delivery Batches

### Batch A: Model Lab Artifacts Packaging

Create lightweight, reviewable assets from existing real experiment evidence:
metrics JSON, compact tables, curves, selected predictions, hallucination
examples, and source metadata. Do not load models.

Current status: Batch A packaging is complete as a lightweight artifact package
only. It uses existing offline evidence, does not load models, does not retrain,
does not implement the Model Lab UI, and does not deploy a Space. Batch B waits
for controller review.

### Batch B: Unified Gradio Demo

Add Model Lab and Architecture tabs around the completed Invoice Audit
baseline. Evaluate additional live audit cases without changing Phase 2 rules.

Current status: Batch B is complete locally. The Gradio app contains Invoice
Audit, Model Lab, and Architecture tabs. Model Lab reads existing real offline
lightweight artifacts only. The web UI does not run live LayoutLMv3 or real
LoRA inference. The CPU-only Hugging Face Space is now public; automated HTTP,
configuration, and API checks passed, while a manual visual check remains.

### Batch C: Hugging Face Spaces

Deploy the CPU-only hybrid presentation with fixed fallback after local
verification. No model upload or GPU is required for the default route.

Batch C.1 local packaging, Batch C.2 Space creation, and Batch C.3 controlled
upload are complete. The public app remains CPU-only and contains no model
weights. A manual visual browser check is still required before setting full
online deployment verification to true.

### Batch D: LangChain Policy RAG Comparison

Add a focused comparison that preserves the existing SQLite FTS5 policy path
and measures whether LangChain adds clear engineering value.

### Batch E: Docker Compose + GitHub Actions CI

Complete reproducible service startup and automated pytest/model smoke checks.

### Batch F: README + Demo GIF + Resume

Package the final project narrative, visual walkthrough, measured claims, and
resume bullets.

### Batch G: Optional Live Inference Feasibility

Measure checkpoint hosting, CPU/GPU latency, memory, cold start, and download
behavior before deciding whether to expose online LayoutLMv3 or real LoRA.

## 5. Capability Coverage

The frozen route keeps the original project goals visible:

- PyTorch and Transformers through LayoutLMv3 training evidence;
- LoRA/QLoRA through two real Qwen experiments and failure analysis;
- FastAPI, SQLite, Agent tools, deterministic matching, and Risk Engine through
  the live audit tab;
- RAG through the live Policy RAG path and later LangChain comparison;
- high-risk AI governance through Canonical Facts, Guard, Fallback, and Audit
  Trail;
- delivery engineering through later Spaces, Docker Compose, GitHub Actions
  CI, README, and Demo assets.

Stability and model visibility are complementary requirements. The portfolio
Demo must show both without claiming that offline model evidence is live.
