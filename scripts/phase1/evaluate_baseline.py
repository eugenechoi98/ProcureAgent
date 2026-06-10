"""运行 fixture/真实 SROIE OCR + Regex baseline 评测。"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.baseline import SroieRegexBaseline
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.error_analysis import collect_error_cases, errors_to_json
from procureguard.extraction.metrics import build_evaluation_report, metrics_to_markdown, write_json_report


def main() -> None:
    """读取 processed JSONL，输出字段级评测报告。"""

    parser = argparse.ArgumentParser(description="Evaluate SROIE OCR regex baseline.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--data-source", default="sroie")
    parser.add_argument("--evaluation-split", default="unspecified")
    parser.add_argument("--fixture", action="store_true", help="Mark report as fixture smoke result.")
    args = parser.parse_args()

    started_at = time.perf_counter()
    samples = read_processed_jsonl(args.input)
    if not any(any(value for value in sample.labels.values()) for sample in samples):
        raise SystemExit(
            "No company/address/date/total ground truth found. "
            "Refusing to calculate field F1 for unlabeled data."
        )
    baseline = SroieRegexBaseline()
    predictions = [baseline.extract(sample.tokens).values() for sample in samples]
    references = [sample.labels for sample in samples]
    report = build_evaluation_report(
        baseline_name=baseline.baseline_name,
        predictions=predictions,
        references=references,
        sample_count=len(samples),
        data_source=args.data_source,
        is_fixture=args.fixture,
        started_at=started_at,
    )
    sample_ids = [sample.sample_id for sample in samples]
    errors = collect_error_cases(sample_ids, predictions, references)
    report["evaluation_split"] = args.evaluation_split
    report["error_count"] = len(errors)
    report["error_count_by_field"] = dict(Counter(error.field for error in errors))
    report["error_type_distribution"] = dict(Counter(error.error_type for error in errors))
    report["errors"] = errors_to_json(errors[:20])

    write_json_report(report, args.output)
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(metrics_to_markdown(report), encoding="utf-8")
    print(f"sample_count={len(samples)}")
    for metric in report["metrics"]:
        print(
            f"{metric['field']}: precision={metric['precision']:.4f} "
            f"recall={metric['recall']:.4f} f1={metric['f1']:.4f} "
            f"support={metric['support']}"
        )
    print(f"error_count={len(errors)}")
    print(f"runtime_seconds={report['runtime_seconds']}")
    print(f"evaluation_split={args.evaluation_split}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
