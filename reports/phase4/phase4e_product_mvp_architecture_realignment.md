# Phase 4E-R Product MVP Architecture Realignment Report

## Status

`completed`

ProcureGuard AI is realigned as an open-source, locally runnable, real-user-experience research MVP. The immediate route is no longer SQLite-first and is not limited to offline evidence presentation.

## Decisions

- Live local OCR + LayoutLMv3 extraction is a core follow-up path, starting as a bounded spike.
- OCR supplies tokens and bounding boxes; LayoutLMv3 produces field candidates.
- A human confirmation/correction gate separates extraction errors from procurement anomalies.
- Phase 2 deterministic matching, Policy RAG and Risk Engine remain the sole source of risk and action decisions.
- Deterministic template remains the default explanation.
- LoRA is limited to an opt-in controlled rewrite candidate after facts are frozen; Guard failure always falls back.
- LangChain comparison follows the core image-to-audit integration and cannot replace the formal Policy RAG path.
- SQLite persistence, Docker hardening, HF live inference, auth and multi-tenancy are deferred until their product need is demonstrated.

## Roadmap

| Phase | Outcome |
|---|---|
| 4E | Product MVP architecture realignment complete |
| 4F | Local live OCR / LayoutLMv3 extraction spike |
| 4G | Field confirmation and Phase 2 audit integration |
| 4H | Guarded explanation runtime integration |
| 4I | LangChain Policy RAG comparison |
| 4J | Open-source release readiness |

## Boundary

The current HF Space may remain a stable portfolio demo. The repository is not an enterprise procurement system, does not authorize payment, and does not yet provide production data governance, authentication, multi-tenancy or ERP integration.

Detailed rationale and acceptance gates are in [the architecture realignment document](../../docs/phase4e_product_mvp_architecture_realignment.md).
