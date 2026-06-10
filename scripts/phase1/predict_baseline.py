"""对无实体标签的真实 SROIE 镜像运行 baseline 预测。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.baseline import SroieRegexBaseline
from procureguard.extraction.datasets import read_processed_jsonl


def main() -> None:
    """输出真实样本的 baseline 预测，不计算无 ground truth 的 F1。"""

    parser = argparse.ArgumentParser(description="Predict SROIE fields without ground truth scoring.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    samples = read_processed_jsonl(args.input)
    baseline = SroieRegexBaseline()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    field_counts = {"company": 0, "address": 0, "date": 0, "total": 0}
    with args.output.open("w", encoding="utf-8") as handle:
        for sample in samples:
            extraction = baseline.extract(sample.tokens)
            values = extraction.values()
            for field_name, value in values.items():
                field_counts[field_name] += int(value is not None)
            handle.write(
                json.dumps(
                    {
                        "sample_id": sample.sample_id,
                        "baseline_name": extraction.baseline_name,
                        "fields": {
                            name: field.__dict__
                            for name, field in extraction.fields.items()
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"sample_count={len(samples)}")
    print(f"field_prediction_counts={field_counts}")
    print("evaluation_status=not_scored_missing_entity_ground_truth")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
