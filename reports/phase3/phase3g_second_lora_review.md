# Phase 3G.1 Second LoRA Real Evaluation Review

## Conclusion

Phase 3G.1 records the second real QLoRA evaluation on ModelScope. The run used the same model, split, seed, and training parameters as the first real run. The only intended variable was the Phase 3F fact-constrained prompt and unified structured gold answer.

The second adapter did not pass the deployment hard gates. It must not be connected to the API, must not become the default user-facing explanation path, and should remain experimental shadow evidence only.

## Source And Artifact Status

- Baseline commit: `4eeb28c77fc740690cefb2a872d27328c2b9be52`
- Cloud run status: user-confirmed real ModelScope run
- Local second-run artifact copy: not present in this workspace
- Artifact isolation: Phase 3F.1 introduced `PHASE3_ARTIFACT_DIR` and the recommended isolated directory `artifacts/phase3_runs/phase3g_second_lora_run`
- First-run report remains separate: `reports/phase3/phase3e_lora_review.json`

This report records the confirmed cloud metrics without copying checkpoint, adapter, prediction, or real runtime artifacts into Git.

## Runtime

| item | value |
| --- | --- |
| GPU | NVIDIA A10 |
| model | Qwen/Qwen2.5-0.5B-Instruct |
| backend | qlora_4bit_bitsandbytes |
| torch | 2.2.2+cu118 |
| CUDA | 11.8 |
| numpy | 1.26.4 |
| bitsandbytes | 0.44.1 |
| transformers | 4.46.3 |

## Dataset And Training Parameters

| item | value |
| --- | ---: |
| seed | 42 |
| train | 160 |
| validation | 20 |
| test | 20 |
| epochs | 3 |
| batch size | 2 |
| gradient accumulation | 8 |
| max sequence length | 1024 |
| learning rate | 0.0002 |
| LoRA r | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |

No epoch, learning rate, LoRA rank, batch size, model, split, or evaluator setting was changed.

## Training Loss

| epoch | train loss | validation loss |
| ---: | ---: | ---: |
| 1 | 1.459200 | 0.873569 |
| 2 | 0.276200 | 0.205891 |
| 3 | 0.145800 | 0.139261 |

## Test Metrics

| metric | base | fine-tuned | hard gate |
| --- | ---: | ---: | ---: |
| format_compliance | 0.0000 | 0.0000 | >= 0.9000 |
| factual_consistency | 1.0000 | 0.9000 | >= 0.9500 |
| action_consistency | 0.0500 | 0.4500 | >= 0.9000 |
| anomaly_coverage | 0.5000 | 0.4250 | >= 0.9000 |
| hallucination_rate | 0.0500 | 0.1500 | <= 0.0500 |

The fine-tuned adapter failed every deployment gate. The fact-constrained prompt and unified gold answer improved the data contract, but did not make the small model stable enough for fact-sensitive procurement audit explanations.

## Hallucination Examples

| sample_id | issue |
| --- | --- |
| phase3-missing_po_number-024 | unknown_identifier:PO-77450099 |
| phase3-missing_goods_receipt-023 | unknown_identifier:GRN-unknown |
| phase3-multi_issue_combination-024 | unsupported_policy_or_approver:审批人 |

## Decisions

- Do not start a third training run immediately.
- Do not integrate the adapter into the API.
- Do not present LoRA as the official default explainer.
- Move to Phase 3H guarded explanation architecture.
- Use deterministic template output as the MVP official explanation path.
- Keep LoRA as shadow or future controlled rewrite only after it passes both hard gates and output guard.

## Next Phase

Phase 3H should design and then implement a guarded explanation layer:

1. Canonical Audit Facts from Phase 2 as the only writable fact source.
2. Deterministic Template Renderer as the default official explanation.
3. Controlled LLM Rewrite as optional language improvement.
4. LoRA Output Guard to reject invented facts or changed decisions.
5. Fallback Orchestrator to return the template on any unsafe condition.
6. Audit Trail for reproducibility and review.
