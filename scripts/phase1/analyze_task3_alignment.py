"""生成 SROIE Task 3 BIO alignment 精简报告。"""

from __future__ import annotations

import argparse
from collections import Counter
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.alignment import align_samples
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.schemas import SROIE_FIELDS


def main() -> None:
    """统计字段对齐率并写 Markdown。"""

    parser = argparse.ArgumentParser(description="Analyze Task 3 BIO alignment.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    samples = read_processed_jsonl(args.input)
    _, summary = align_samples(samples)
    missing_by_field = Counter(case.field for case in summary.unaligned_cases)
    totals_by_field = {
        field_name: sum(bool(sample.labels.get(field_name)) for sample in samples)
        for field_name in SROIE_FIELDS
    }
    aligned_by_field = {
        field_name: totals_by_field[field_name] - missing_by_field[field_name]
        for field_name in SROIE_FIELDS
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SROIE Task 3 BIO Alignment Summary",
        "",
        f"- sample_count: {summary.sample_count}",
        f"- total_fields: {summary.total_fields}",
        f"- aligned_fields: {summary.aligned_fields}",
        f"- unaligned_fields: {summary.unaligned_fields}",
        "",
        "| field | total | aligned | unaligned | success_rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for field_name in SROIE_FIELDS:
        total = totals_by_field[field_name]
        aligned = aligned_by_field[field_name]
        rate = aligned / total if total else 0.0
        lines.append(
            f"| {field_name} | {total} | {aligned} | {missing_by_field[field_name]} | {rate:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Representative Unaligned Cases",
            "",
            "| sample_id | field | reason |",
            "| --- | --- | --- |",
        ]
    )
    for case in summary.unaligned_cases[:10]:
        lines.append(f"| {case.sample_id} | {case.field} | {case.reason} |")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sample_count={summary.sample_count}")
    print(f"total_fields={summary.total_fields}")
    print(f"aligned_fields={summary.aligned_fields}")
    print(f"unaligned_fields={summary.unaligned_fields}")
    print(f"aligned_by_field={aligned_by_field}")
    print(f"unaligned_by_field={dict(missing_by_field)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
