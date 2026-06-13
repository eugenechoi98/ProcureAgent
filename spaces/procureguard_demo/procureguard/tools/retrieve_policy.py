"""政策检索工具。"""

import sqlite3

from procureguard.models.tools import PolicySearchResult
from procureguard.services.policy_rag import PolicyRAG


def retrieve_policy(
    conn: sqlite3.Connection,
    query: str,
    top_k: int = 3,
) -> list[PolicySearchResult]:
    """调用 Policy RAG 检索政策条款。"""

    return PolicyRAG(conn).retrieve(query=query, top_k=top_k)
