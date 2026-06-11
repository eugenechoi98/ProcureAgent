"""Phase 3B：base model inference smoke 入口，默认 dry-run。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.gpu_notebook import run_base_inference_smoke


def main() -> None:
    """默认只打印计划，显式 --run 才加载模型。"""

    parser = ArgumentParser()
    parser.add_argument("--model-dir")
    parser.add_argument("--sample-count", type=int, default=1)
    parser.add_argument("--output-name", default="base_smoke.jsonl")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    plan = run_base_inference_smoke(
        PROJECT_ROOT,
        model_dir=args.model_dir,
        sample_count=args.sample_count,
        run=args.run,
        output_name=args.output_name,
    )
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
