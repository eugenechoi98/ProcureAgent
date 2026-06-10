"""把 SROIE raw 目录转换为 Phase 1 processed JSONL。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import iter_sroie_samples, write_processed_jsonl


def main() -> None:
    """执行 SROIE 转换。"""

    parser = argparse.ArgumentParser(description="Prepare SROIE processed JSONL.")
    parser.add_argument("--input", required=True, help="SROIE raw directory.")
    parser.add_argument("--output", required=True, help="Output processed JSONL path.")
    args = parser.parse_args()

    samples = iter_sroie_samples(args.input)
    write_processed_jsonl(samples, args.output)
    print(f"prepared_samples={len(samples)} output={args.output}")


if __name__ == "__main__":
    main()
