"""基于 SQLite FTS5 的 Policy RAG 简化实现。"""

import sqlite3

from procureguard.models.invoice import ExtractedFields, ValidationResult
from procureguard.models.tools import PolicySearchResult


class PolicyRAG:
    """用 BM25 从 mock 政策表检索相关规则。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def retrieve(self, query: str, top_k: int = 3) -> list[PolicySearchResult]:
        """按关键词检索政策，返回 top_k 条。"""

        rows = self.conn.execute(
            """
            SELECT
                policy_documents.id AS policy_id,
                policy_documents.section AS section,
                policy_documents.content AS policy_text,
                bm25(policy_fts) AS relevance_score
            FROM policy_fts
            JOIN policy_documents ON policy_fts.rowid = policy_documents.rowid
            WHERE policy_fts MATCH ?
            ORDER BY relevance_score
            LIMIT ?
            """,
            (query, top_k),
        ).fetchall()
        return [PolicySearchResult(**dict(row)) for row in rows]

    def check_policy_violation(
        self,
        invoice: ExtractedFields,
        validation: ValidationResult,
    ) -> list[str]:
        """根据共享模型生成演示用政策违规标记。"""

        flags: list[str] = []
        if invoice.total_amount and invoice.total_amount > 10_000:
            flags.append("high_value_approval_required")
        if not validation.po_match:
            flags.append("missing_or_invalid_po")
        if not validation.grn_match:
            flags.append("goods_receipt_mismatch")
        if not validation.amount_match:
            flags.append("amount_discrepancy")
        if not validation.duplicate_check:
            flags.append("duplicate_invoice")
        if validation.mismatches:
            flags.append("manual_review_required")
        return list(dict.fromkeys(flags))
