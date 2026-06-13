"""离线 LangChain Policy RAG 兼容实验。"""

from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field

from procureguard.db.seed_policies import MOCK_POLICIES


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
QUERY_ALIASES = {
    "authorization": ("approval",),
    "bill": ("invoice",),
    "boss": ("manager",),
    "receipt": ("grn", "goods", "receipt"),
    "supplier": ("vendor",),
}


def build_policy_documents() -> list[Document]:
    """从项目内置政策语料构建 LangChain Document。"""

    return [
        Document(
            page_content=policy["content"],
            metadata={
                "policy_id": f"policy_{index:03d}",
                "section": policy["section"],
                "source": "procureguard.db.seed_policies.MOCK_POLICIES",
            },
        )
        for index, policy in enumerate(MOCK_POLICIES, start=1)
    ]


class OfflinePolicyRetriever(BaseRetriever):
    """使用本地词法评分的最小 LangChain Retriever。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    documents: list[Document] = Field(default_factory=build_policy_documents)
    top_k: int = 3

    def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Document]:
        return [item["document"] for item in self.search_with_scores(query)]

    def search_with_scores(self, query: str) -> list[dict[str, Any]]:
        """返回命中文档、分数和可审计的匹配词。"""

        query_tokens = _expand_query_tokens(query)
        document_tokens = [_document_tokens(document) for document in self.documents]
        document_frequency = Counter(
            token for tokens in document_tokens for token in set(tokens)
        )
        scored: list[dict[str, Any]] = []
        normalized_query = query.strip().lower()

        for document, tokens in zip(self.documents, document_tokens, strict=True):
            matched = sorted(set(query_tokens).intersection(tokens))
            score = sum(
                1.0 + math.log((len(self.documents) + 1) / (document_frequency[token] + 1))
                for token in matched
            )
            policy_id = str(document.metadata["policy_id"]).lower()
            if normalized_query == policy_id:
                score += 100.0
                matched.append(policy_id)
            if score <= 0:
                continue
            scored.append(
                {
                    "document": document,
                    "score": round(score, 6),
                    "matched_terms": sorted(set(matched)),
                }
            )

        scored.sort(
            key=lambda item: (
                -item["score"],
                item["document"].metadata["policy_id"],
            )
        )
        return scored[: self.top_k]


def _expand_query_tokens(query: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(query.lower())
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(QUERY_ALIASES.get(token, ()))
    return expanded


def _document_tokens(document: Document) -> list[str]:
    metadata = document.metadata
    text = " ".join(
        [
            document.page_content,
            str(metadata.get("section", "")),
            str(metadata.get("policy_id", "")),
        ]
    )
    return TOKEN_PATTERN.findall(text.lower())
