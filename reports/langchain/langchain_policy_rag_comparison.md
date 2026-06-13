# LangChain Policy RAG Comparison

SQLite FTS5/BM25 remains the official main chain. The LangChain path is an offline, deterministic compatibility benchmark only.

| Case | Baseline top 1 | LangChain top 1 | Baseline recall@3 | LangChain recall@3 |
| --- | --- | --- | ---: | ---: |
| exact_keyword | policy_004 | policy_004 | 1.000 | 1.000 |
| policy_id_lookup | none | policy_006 | 0.000 | 1.000 |
| amount_threshold | policy_006 | policy_006 | 1.000 | 1.000 |
| approval_requirement | policy_002 | policy_002 | 1.000 | 1.000 |
| semantic_like_paraphrase | none | policy_001 | 0.000 | 1.000 |
| multi_term_query | policy_003 | policy_003 | 1.000 | 1.000 |
| missing_policy | none | none | 1.000 | 1.000 |
| ambiguous_query | policy_001 | policy_001 | 1.000 | 1.000 |

## Boundaries

- Local mock policy corpus only.
- No network, embedding API, LLM API, API key, model, or GPU.
- The paraphrase case uses a declared lexical alias map; it is not semantic embedding retrieval.
- Latency is a local micro-benchmark and is not a production performance claim.
