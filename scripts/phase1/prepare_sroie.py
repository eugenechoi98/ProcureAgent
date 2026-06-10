"""把 SROIE raw 目录转换为 Phase 1 processed JSONL。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import check_sroie_dataset, iter_sroie_samples, write_processed_jsonl


def main() -> None:
    """执行 SROIE 转换。"""

    parser = argparse.ArgumentParser(description="Prepare SROIE processed JSONL.")
    parser.add_argument("--input", required=True, help="SROIE raw directory.")
    parser.add_argument("--output", required=True, help="Output processed JSONL path.")
    args = parser.parse_args()

    check = check_sroie_dataset(args.input)
    if not check.exists or check.sample_count == 0:
        raise SystemExit(
            "SROIE input is missing or empty. Expected img/, box/, key/ or entities/ under the input path."
        )
    samples, errors = iter_sroie_samples(args.input, strict=False)
    write_processed_jsonl(samples, args.output)
    for error in errors:
        print(f"warning={error}")
    if not samples:
        raise SystemExit("No valid SROIE samples were prepared.")
    print(
        f"total_samples={check.sample_count} success={len(samples)} failed={len(errors)} "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
