# Phase 4F.1 LayoutLMv3 Runtime Asset Bundle Report

## Status

- Phase 4F.1 engineering work: `completed`
- Runtime asset bundle: `blocked_missing_checkpoint`
- Fine-tuned checkpoint found: `false`
- Saved processor found: `false`
- Label map rebuilt: `false` because checkpoint label order cannot be verified without checkpoint config
- Real live extraction completed: `false`
- Fake fixture used: `true`, contract tests only
- Fake fixture counts as live success: `false`
- Phase 2 invoked: `false`
- Risk/action generated: `false`
- Model downloaded: `false`
- Model weights committed: `false`

## Audit Findings

The Phase 1 Notebook saved both model and processor to `checkpoints/phase1/layoutlmv3_best` and created `layoutlmv3_best.zip`. The completed validation inference therefore had a real cloud/runtime checkpoint, but that bundle was not returned to this local workspace.

The local Hugging Face cache contains a complete public `microsoft/layoutlmv3-base` snapshot. It was deliberately not used as the fine-tuned checkpoint. The Phase 1 BIO definitions are available in source code, but the label map was not generated into the blocked bundle because the missing checkpoint config prevents proof that label order matches.

## Actual Prepare Run

- Output: ignored `artifacts/phase1_runtime/layoutlmv3_sroie_corrected`
- Exit code: `2`
- Manifest status: `blocked_missing_checkpoint`
- Download attempted: `false`
- Public sample checked: `demo/e2e_cases/case_a_standard_pass/source_invoice.png`
- Sample exists: `true`
- Checker failures: `missing_checkpoint`, `missing_processor`, `missing_label_map`

No live field candidates or latency are reported. The next action is to retrieve the original `layoutlmv3_best.zip` from the ModelScope/Colab training environment or its persisted storage, then rerun prepare, checker and spike.

See [the runtime bundle guide](../../docs/phase4f1_layoutlmv3_runtime_asset_bundle.md).
