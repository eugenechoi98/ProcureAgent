"""LangChain Policy RAG benchmark 测试。"""

from pathlib import Path

from scripts.benchmark.run_langchain_policy_rag_comparison import (
    run_benchmark,
    write_reports,
)


def test_benchmark_covers_required_cases_and_boundaries() -> None:
    result = run_benchmark()

    assert result["ready"] is True
    assert result["case_count"] == 8
    assert {case["case_id"] for case in result["cases"]} == {
        "exact_keyword",
        "policy_id_lookup",
        "amount_threshold",
        "approval_requirement",
        "semantic_like_paraphrase",
        "multi_term_query",
        "missing_policy",
        "ambiguous_query",
    }
    assert result["official_main_chain"] == "sqlite_fts5_bm25"
    assert result["network_used"] is False
    assert result["embedding_api_used"] is False
    assert result["llm_api_used"] is False
    assert result["database_written"] is False
    assert all(case["source_integrity"] for case in result["cases"])


def test_benchmark_ranking_is_repeatable() -> None:
    first = run_benchmark()
    second = run_benchmark()

    first_rankings = [case["langchain"]["hit_policy_ids"] for case in first["cases"]]
    second_rankings = [case["langchain"]["hit_policy_ids"] for case in second["cases"]]
    assert first_rankings == second_rankings


def test_benchmark_writes_json_and_markdown(tmp_path: Path) -> None:
    result = run_benchmark()
    json_path = tmp_path / "comparison.json"
    markdown_path = tmp_path / "comparison.md"

    write_reports(result, json_path, markdown_path)

    assert json_path.exists()
    assert markdown_path.exists()
    assert "SQLite FTS5/BM25 remains the official main chain" in markdown_path.read_text(encoding="utf-8")

