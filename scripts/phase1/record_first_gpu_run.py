"""固化首轮 GPU 训练结果并生成日期与 hybrid 报告。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.phase1_results import (
    analyze_date_validation,
    date_analysis_to_markdown,
    hybrid_metrics,
    hybrid_report_to_markdown,
    write_first_gpu_outputs,
)


def main() -> None:
    """生成可提交的精简首轮训练报告。"""

    parser = argparse.ArgumentParser(description="Record first Phase 1 GPU run.")
    parser.add_argument(
        "--validation",
        type=Path,
        default=PROJECT_ROOT / "data/phase1/sroie_task3/processed/validation.jsonl",
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=PROJECT_ROOT / "reports/phase1",
    )
    args = parser.parse_args()

    training_paths = write_first_gpu_outputs(args.reports / "gpu_training")
    samples = read_processed_jsonl(args.validation)
    date_report = analyze_date_validation(samples)
    date_path = args.reports / "layoutlmv3_date_error_analysis.md"
    date_path.write_text(date_analysis_to_markdown(date_report), encoding="utf-8")
    errors_path = args.reports / "layoutlmv3_validation_errors.md"
    metric = date_report["date_metric"]
    errors_path.write_text(
        "\n".join(
            [
                "# First GPU Run Validation Error Summary",
                "",
                "- evaluation_split: local_validation_split_seed_42",
                "- official_test: false",
                "- cloud_prediction_details_available: false",
                "",
                "| field | false_positive | false_negative |",
                "| --- | ---: | ---: |",
                "| company | 19 | 54 |",
                "| address | 36 | 38 |",
                f"| date | {metric['false_positive']} | {metric['false_negative']} |",
                "| total | 9 | 17 |",
                "",
                "逐样本云端预测尚未回传，因此不伪造模型错误案例。"
                "可验证的日期 OCR、alignment、候选、截断和重建证据见 "
                "`layoutlmv3_date_error_analysis.md`。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    hybrid_path = args.reports / "hybrid_extraction_validation_report.md"
    hybrid_path.write_text(
        hybrid_report_to_markdown(hybrid_metrics()),
        encoding="utf-8",
    )
    print(f"training_outputs={training_paths}")
    print(f"date_report={date_path}")
    print(f"errors_report={errors_path}")
    print(f"hybrid_report={hybrid_path}")


if __name__ == "__main__":
    main()
