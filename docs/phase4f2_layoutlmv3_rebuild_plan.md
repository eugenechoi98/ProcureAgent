# Phase 4F.2 LayoutLMv3 Rebuild Plan

## Trigger

Use this plan only if `layoutlmv3_best.zip` and equivalent Phase 1 checkpoint artifacts cannot be recovered.
The recovery orchestrator must not start training automatically.

## Dataset

- Source: Phase 1 SROIE / Voxel51 scanned_receipts Task 3 processed data.
- Split: `local_validation_split_seed_42` with 570 train and 142 validation samples.
- Images: SROIE receipt images resolved by the existing Phase 1 path resolver.
- No real enterprise invoices are used.

## Label Schema

Use the existing nine BIO labels from `procureguard.extraction.alignment`:

```text
O
B-COMPANY / I-COMPANY
B-ADDRESS / I-ADDRESS
B-DATE / I-DATE
B-TOTAL / I-TOTAL
```

Do not change label order or field names. The new run must emit `label_map.json` and checkpoint `config.json` with identical id2label order.

## Training Config

- Base model: `microsoft/layoutlmv3-base`, loaded locally with `use_safetensors=True`.
- Epochs: 5.
- Batch size: 2, reduce to 1 on CUDA OOM.
- Gradient accumulation steps: 4.
- Learning rate: 1e-5.
- Weight decay: 0.01.
- Max grad norm: 1.0.
- Seed: 42.
- Save target: `checkpoints/phase1/layoutlmv3_best/`.
- Runtime artifact name: `retrained_layoutlmv3_v2`.

## Expected Compute

- Preferred: NVIDIA A10-class GPU or equivalent.
- Previous observed run: about 2 minutes per epoch on A10, roughly 10-15 minutes total plus validation/export overhead.
- CPU training is not recommended for this fallback.

## Reproducibility Steps

1. Confirm user explicitly says `允许重训`.
2. Verify Phase 1 processed JSONL and images are present.
3. Run the approved `scripts/phase1/retrain_layoutlmv3.py` only after approval.
4. Save model and processor with `save_pretrained`.
5. Generate `label_map.json` from the verified BIO schema.
6. Run `scripts/phase4/prepare_layoutlmv3_runtime_assets.py`.
7. Run the Phase 4F asset checker and live extraction spike.
8. Record metrics separately as retrained v2; do not overwrite prior Phase 1 evidence claims.

## Risks

- Re-run metrics may differ from the original checkpoint.
- Dataset path or OCR annotation drift can change results.
- Label order mismatch would invalidate token classification outputs.
- Model weights, checkpoints and caches must remain outside Git.
- Rebuilt v2 must not be described as the original Phase 1 checkpoint.
