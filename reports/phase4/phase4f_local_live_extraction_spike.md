# Phase 4F Local Live Extraction Spike Report

## Result

- Engineering spike status: `completed`
- Real live extraction success: `false`
- Blocking reason: the Phase 1 fine-tuned checkpoint directory, saved processor files and checkpoint `id2label` configuration are not present in this workspace.
- Dependencies found: Pillow, PaddleOCR, PaddlePaddle, Torch and Transformers.
- Runtime plan: CPU allowed; CUDA unavailable.
- Model download attempted: `false`
- Model weights committed: `false`
- HF Demo modified: `false`
- Phase 2 invoked: `false`
- Risk/action generated: `false`

The repository-local Hugging Face cache contains the public LayoutLMv3 base model only. It was not used as a substitute for the fine-tuned Phase 1 checkpoint.

## Delivered

- Read-only asset checker with JSON output and no model initialization.
- Local spike command with offline-only checkpoint/processor loading.
- OCR token, field candidate, environment, Markdown report and optional bbox visualization contracts.
- Machine-readable fail-closed output for missing assets, invalid images, OCR failures and model failures.
- Candidate provenance and mandatory human-confirmation markers.
- Tests using synthetic image/token/model fixtures; fake runtime tests validate contracts only and are not reported as live model success.

## Actual Asset Check

| Item | Result |
|---|---|
| `checkpoints/phase1/layoutlmv3_best` | missing |
| fine-tuned `model.safetensors` | missing |
| saved processor | missing |
| checkpoint BIO label map | missing |
| PaddleOCR/PaddlePaddle import | available |
| Torch/Transformers/Pillow import | available |
| CUDA | unavailable |
| CPU inference policy | allowed |

No real inference latency or extracted values are reported because the required fine-tuned assets are absent. The committed Phase 1 metric remains offline checkpoint evidence, not this spike's live result.

## Decision

Phase 4G should wait until one real local run succeeds using the matching fine-tuned checkpoint and a public or synthetic invoice image. This prevents a fake-runtime schema test or base-model cache from being mistaken for product extraction capability.

See [the Phase 4F guide](../../docs/phase4f_local_live_extraction_spike.md).
