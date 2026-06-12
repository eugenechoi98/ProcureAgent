"""Phase 3B：为 LoRA Notebook 生成可写 bootstrap guard。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.gpu_notebook import bootstrap_notebook


def main() -> None:
    """执行可写 bootstrap，不安装依赖、不下载模型。"""

    parser = ArgumentParser()
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--model-dir")
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    guard = bootstrap_notebook(
        PROJECT_ROOT,
        require_cuda=args.require_cuda,
        model_dir=args.model_dir,
        artifact_dir=args.artifact_dir,
    )
    print(json.dumps(guard, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
