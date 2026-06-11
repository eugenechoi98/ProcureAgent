"""使用统一 rubric 评测 base 或 fine-tuned 异常说明。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.evaluation import (
    comparison_to_markdown,
    evaluate_predictions,
    load_predictions,
    load_samples,
)


def main() -> None:
    """评测一个或两个模型结果，不生成虚构指标。"""

    parser = ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--base-predictions", type=Path)
    parser.add_argument("--fine-tuned-predictions", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    prediction_paths = {
        name: path
        for name, path in {
            "base": args.base_predictions,
            "fine_tuned": args.fine_tuned_predictions,
        }.items()
        if path is not None
    }
    if not prediction_paths:
        parser.error("至少提供 --base-predictions 或 --fine-tuned-predictions")

    samples = load_samples(args.dataset)
    reports = {
        name: evaluate_predictions(samples, load_predictions(path))
        for name, path in prediction_paths.items()
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (args.output_dir / "evaluation.md").write_text(
        comparison_to_markdown(reports), encoding="utf-8", newline="\n"
    )
    print(json.dumps({name: value["metrics"] for name, value in reports.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
