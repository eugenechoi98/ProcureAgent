"""运行不依赖模型的 synthetic AuditReport smoke。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from procureguard.db import initialize_database, seed_mock_data, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.models.invoice import ExtractedFields
from procureguard.repositories import InvoiceRepository
from procureguard.services import AgentInvoiceProcessor


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "samples" / "invoices" / "clean_invoice.json"


def run_sample(input_path: Path) -> dict:
    """使用内存数据库运行现有确定性审核主链。"""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    extracted_fields = ExtractedFields.model_validate(payload)
    invoice_id = "sample-clean-invoice"

    conn = get_connection(":memory:")
    try:
        initialize_database(conn)
        seed_mock_data(conn)
        seed_policy_documents(conn)
        InvoiceRepository(conn).create_invoice(
            invoice_id=invoice_id,
            file_path="samples/invoices/clean_invoice.json",
            file_hash="synthetic-sample-clean-invoice-v1",
        )
        report = AgentInvoiceProcessor(conn).process_extracted_invoice(
            invoice_id,
            extracted_fields,
        )
        return report.model_dump(mode="json")
    finally:
        conn.close()


def main() -> int:
    """解析参数并把 AuditReport JSON 输出到 stdout。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    try:
        result = run_sample(args.input.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Sample audit failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
