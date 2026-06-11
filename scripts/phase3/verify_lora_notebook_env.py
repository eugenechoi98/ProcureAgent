"""Phase 3B：只读验证 LoRA Notebook 环境。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.gpu_notebook import verify_notebook_env


def main() -> None:
    """执行只读环境验证。"""

    parser = ArgumentParser()
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--model-dir")
    args = parser.parse_args()
    guard = verify_notebook_env(
        PROJECT_ROOT,
        require_cuda=args.require_cuda,
        model_dir=args.model_dir,
    )
    print(json.dumps(guard, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
