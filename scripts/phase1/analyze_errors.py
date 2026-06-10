"""从 baseline report 输出错误分析 Markdown 或 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main() -> None:
    """读取评测报告并输出错误案例。"""

    parser = argparse.ArgumentParser(description="Write baseline error analysis.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    errors = report.get("errors", [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() == ".json":
        args.output.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        lines = [
            "# Phase 1 Baseline Error Analysis",
            "",
            f"- error_count: {report.get('error_count', len(errors))}",
            f"- error_count_by_field: {report.get('error_count_by_field', {})}",
            f"- error_type_distribution: {report.get('error_type_distribution', {})}",
            "",
            "## Representative Cases",
            "",
            "| sample_id | field | predicted | ground_truth | error_type | notes |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for error in errors[:10]:
            lines.append(
                f"| {error.get('sample_id', '')} | {error.get('field', '')} | "
                f"{error.get('predicted') or ''} | {error.get('ground_truth') or ''} | "
                f"{error.get('error_type', 'unknown')} | {error.get('notes', '')} |"
            )
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"error_count={report.get('error_count', len(errors))}")
    print(f"error_count_by_field={report.get('error_count_by_field', {})}")
    print(f"error_type_distribution={report.get('error_type_distribution', {})}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
