"""审计轨迹 SQLite CRUD。"""

import sqlite3
import time
from typing import Any
from uuid import uuid4

from procureguard.db.json_utils import dumps_json, loads_json


class AuditTraceRepository:
    """封装 audit_traces 表的基础操作。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_trace(
        self,
        invoice_id: str,
        step_name: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        latency_ms: int | None = None,
    ) -> dict[str, Any]:
        """创建一条审计轨迹。"""

        trace_id = f"trace_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO audit_traces
            (id, invoice_id, step_name, input_json, output_json, tool_calls_json, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                invoice_id,
                step_name,
                dumps_json(input_data or {}),
                dumps_json(output_data or {}),
                dumps_json(tool_calls or []),
                latency_ms,
                time.time_ns(),
            ),
        )
        self.conn.commit()
        return self._get_trace(trace_id)

    def list_traces(self, invoice_id: str) -> list[dict[str, Any]]:
        """按创建时间查询发票轨迹。"""

        rows = self.conn.execute(
            """
            SELECT * FROM audit_traces
            WHERE invoice_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (invoice_id,),
        ).fetchall()
        return [self._row_to_trace(row) for row in rows]

    def _get_trace(self, trace_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM audit_traces WHERE id = ?",
            (trace_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Trace {trace_id} was not created.")
        return self._row_to_trace(row)

    def _row_to_trace(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "invoice_id": row["invoice_id"],
            "step_name": row["step_name"],
            "input": loads_json(row["input_json"], {}),
            "output": loads_json(row["output_json"], {}),
            "tool_calls": loads_json(row["tool_calls_json"], []),
            "latency_ms": row["latency_ms"],
            "created_at": row["created_at"],
        }
