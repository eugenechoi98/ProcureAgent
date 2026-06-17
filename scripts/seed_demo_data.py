"""预置 ProcureGuard 演示用 mock PO/GRN 数据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

from procureguard.config import get_settings

warnings.filterwarnings(
    "ignore",
    message='Field name "json" in "ExecuteAuditResponse" shadows an attribute in parent "BaseModel"',
    category=UserWarning,
)

from procureguard.productization.demo_seed import seed_demo_database_file


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-path",
        type=Path,
        default=None,
        help="SQLite database path. Defaults to DATABASE_PATH or data/procureguard.db.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear and reinsert demo PO/GRN records managed by this script.",
    )
    return parser.parse_args()


def main() -> int:
    """执行预置并打印 JSON 摘要。"""

    args = parse_args()
    database_path = args.database_path or get_settings().database_path
    result = seed_demo_database_file(database_path, reset=args.reset)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
