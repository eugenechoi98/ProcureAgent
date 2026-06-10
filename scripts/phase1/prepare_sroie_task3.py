"""转换并固定拆分 Voxel51/scanned_receipts Task 3 数据。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import write_processed_jsonl
from procureguard.extraction.hf_sroie_task3 import convert_task3_dataset, split_task3_samples


def main() -> None:
    """输出 train/validation processed JSONL。"""

    parser = argparse.ArgumentParser(description="Prepare labeled SROIE Task 3 JSONL.")
    parser.add_argument("--input", required=True, type=Path, help="Task 3 dataset root.")
    parser.add_argument("--output", required=True, type=Path, help="Processed output directory.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    samples_path = args.input / "samples.json"
    samples, errors, missing_fields = convert_task3_dataset(samples_path, args.input)
    split = split_task3_samples(samples, seed=args.seed)
    write_processed_jsonl(split.train, args.output / "train.jsonl")
    write_processed_jsonl(split.validation, args.output / "validation.jsonl")
    for error in errors:
        print(f"warning={error}")
    print(f"total={len(samples) + len(errors)}")
    print(f"success={len(samples)}")
    print(f"failed={len(errors)}")
    print(f"missing_fields={missing_fields}")
    print(f"train_count={len(split.train)}")
    print(f"validation_count={len(split.validation)}")
    print(f"seed={split.seed}")
    print(f"evaluation_split={split.evaluation_split}")
    print(f"output_path={args.output}")


if __name__ == "__main__":
    main()
