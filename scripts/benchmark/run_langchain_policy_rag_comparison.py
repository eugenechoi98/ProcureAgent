"""生成 SQLite FTS5 与 LangChain 离线 Retriever 的真实对比报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.db.connection import initialize_database
from procureguard.db.seed_policies import MOCK_POLICIES, seed_policy_documents
from procureguard.integrations.langchain_policy_demo import OfflinePolicyRetriever
from procureguard.services.policy_rag import PolicyRAG

DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "langchain_policy_rag_cases.json"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "reports" / "langchain" / "langchain_policy_rag_comparison.json"
DEFAULT_MARKDOWN_REPORT = PROJECT_ROOT / "reports" / "langchain" / "langchain_policy_rag_comparison.md"


def run_benchmark(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    """在同一份本地政策语料上运行两种检索实现。"""

    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    seed_policy_documents(connection)
    baseline = PolicyRAG(connection)
    retriever = OfflinePolicyRetriever(top_k=3)
    results: list[dict[str, Any]] = []

    try:
        for case in cases:
            query = case["query"]
            expected = case["expected_policy_ids"]

            baseline_start = perf_counter()
            baseline_hits = baseline.retrieve(_fts_query(query), top_k=3)
            baseline_latency = (perf_counter() - baseline_start) * 1000

            langchain_start = perf_counter()
            langchain_hits = retriever.search_with_scores(query)
            langchain_latency = (perf_counter() - langchain_start) * 1000

            baseline_ids = [hit.policy_id for hit in baseline_hits]
            langchain_ids = [hit["document"].metadata["policy_id"] for hit in langchain_hits]
            results.append(
                {
                    "case_id": case["case_id"],
                    "query": query,
                    "expected_policy_ids": expected,
                    "baseline": _result_summary(
                        baseline_ids,
                        expected,
                        baseline_latency,
                        [
                            {
                                "policy_id": hit.policy_id,
                                "section": hit.section,
                                "score": hit.relevance_score,
                            }
                            for hit in baseline_hits
                        ],
                    ),
                    "langchain": _result_summary(
                        langchain_ids,
                        expected,
                        langchain_latency,
                        [
                            {
                                "policy_id": hit["document"].metadata["policy_id"],
                                "section": hit["document"].metadata["section"],
                                "score": hit["score"],
                                "matched_terms": hit["matched_terms"],
                                "source": hit["document"].metadata["source"],
                            }
                            for hit in langchain_hits
                        ],
                    ),
                    "source_integrity": _source_integrity(langchain_hits),
                    "notes": _case_note(case["case_id"]),
                }
            )
    finally:
        connection.close()

    return {
        "ready": True,
        "scope": "offline_local_policy_retrieval_comparison",
        "official_main_chain": "sqlite_fts5_bm25",
        "langchain_role": "optional_compatibility_benchmark_only",
        "network_used": False,
        "embedding_api_used": False,
        "llm_api_used": False,
        "database_written": False,
        "case_count": len(results),
        "summary": {
            "baseline_top1_accuracy": _average(results, "baseline", "top1_hit"),
            "baseline_mean_recall_at_3": _average(results, "baseline", "recall_at_3"),
            "langchain_top1_accuracy": _average(results, "langchain", "top1_hit"),
            "langchain_mean_recall_at_3": _average(results, "langchain", "recall_at_3"),
        },
        "cases": results,
    }


def write_reports(result: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    """写入 JSON 与 Markdown benchmark 证据。"""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# LangChain Policy RAG Comparison",
        "",
        "SQLite FTS5/BM25 remains the official main chain. The LangChain path is an offline, deterministic compatibility benchmark only.",
        "",
        "| Case | Baseline top 1 | LangChain top 1 | Baseline recall@3 | LangChain recall@3 |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for case in result["cases"]:
        lines.append(
            f"| {case['case_id']} | {_top_id(case['baseline'])} | {_top_id(case['langchain'])} | "
            f"{case['baseline']['recall_at_3']:.3f} | {case['langchain']['recall_at_3']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Local mock policy corpus only.",
            "- No network, embedding API, LLM API, API key, model, or GPU.",
            "- The paraphrase case uses a declared lexical alias map; it is not semantic embedding retrieval.",
            "- Latency is a local micro-benchmark and is not a production performance claim.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fts_query(query: str) -> str:
    tokens = [token for token in query.lower().replace("_", " ").split() if token.isalnum()]
    return " OR ".join(f'"{token}"' for token in tokens) or '"__empty__"'


def _result_summary(ids: list[str], expected: list[str], latency_ms: float, hits: list[dict[str, Any]]) -> dict[str, Any]:
    expected_set = set(expected)
    recall = 1.0 if not expected else len(expected_set.intersection(ids)) / len(expected_set)
    return {
        "hit_policy_ids": ids,
        "hits": hits,
        "top1_hit": bool(expected and ids and ids[0] in expected_set) or (not expected and not ids),
        "recall_at_3": round(recall, 6),
        "latency_ms": round(latency_ms, 6),
    }


def _source_integrity(hits: list[dict[str, Any]]) -> bool:
    corpus = {f"policy_{index:03d}": item for index, item in enumerate(MOCK_POLICIES, start=1)}
    return all(
        corpus[hit["document"].metadata["policy_id"]]["content"] == hit["document"].page_content
        for hit in hits
    )


def _case_note(case_id: str) -> str:
    if case_id == "semantic_like_paraphrase":
        return "Uses explicit local lexical aliases; no embedding or semantic model."
    if case_id == "policy_id_lookup":
        return "LangChain metadata lookup is compared with content-only FTS indexing."
    return "Same local policy corpus and top_k=3."


def _average(results: list[dict[str, Any]], path: str, metric: str) -> float:
    return round(sum(float(item[path][metric]) for item in results) / len(results), 6)


def _top_id(summary: dict[str, Any]) -> str:
    return summary["hit_policy_ids"][0] if summary["hit_policy_ids"] else "none"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline LangChain Policy RAG comparison.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_REPORT)
    args = parser.parse_args(argv)
    result = run_benchmark(args.fixture)
    write_reports(result, args.json_output, args.markdown_output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

