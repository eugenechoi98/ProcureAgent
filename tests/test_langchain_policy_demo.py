"""LangChain 本地政策 Retriever 测试。"""

from procureguard.integrations.langchain_policy_demo import (
    OfflinePolicyRetriever,
    build_policy_documents,
)


def test_documents_preserve_local_source_metadata() -> None:
    documents = build_policy_documents()

    assert len(documents) == 10
    assert documents[0].metadata == {
        "policy_id": "policy_001",
        "section": "approval_threshold",
        "source": "procureguard.db.seed_policies.MOCK_POLICIES",
    }


def test_retriever_supports_langchain_invoke_and_scores() -> None:
    retriever = OfflinePolicyRetriever(top_k=3)

    documents = retriever.invoke("duplicate invoice vendor")
    scored = retriever.search_with_scores("duplicate invoice vendor")

    assert documents[0].metadata["policy_id"] == "policy_004"
    assert scored[0]["score"] > 0
    assert "duplicate" in scored[0]["matched_terms"]


def test_policy_id_lookup_is_deterministic() -> None:
    retriever = OfflinePolicyRetriever(top_k=3)

    first = retriever.search_with_scores("policy_006")
    second = retriever.search_with_scores("policy_006")

    assert first == second
    assert first[0]["document"].metadata["policy_id"] == "policy_006"


def test_unknown_query_returns_no_documents() -> None:
    retriever = OfflinePolicyRetriever(top_k=3)

    assert retriever.invoke("carbon emissions sustainability reporting") == []
