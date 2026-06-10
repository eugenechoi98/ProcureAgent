"""只读验证 Phase 1 GPU Notebook 环境和训练 guard。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def parse_args() -> argparse.Namespace:
    """解析环境验证路径。"""

    parser = argparse.ArgumentParser(description="Verify the Phase 1 GPU Notebook environment.")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--runtime", choices=["modelscope", "colab"], required=True)
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Only for local test verification; GPU Notebook must not use this option.",
    )
    return parser.parse_args()


def main() -> None:
    """输出完整验证字段，guard 失败时返回非零状态。"""

    args = parse_args()
    project_root = args.project_root.resolve()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from procureguard.extraction.gpu_notebook import (
        build_gpu_notebook_summary,
        print_summary,
    )

    summary = build_gpu_notebook_summary(
        project_root=project_root,
        processed_dir=args.processed_dir,
        image_root=args.image_root,
        model_dir=args.model_dir,
        runtime=args.runtime,
        require_cuda=not args.allow_cpu,
    )
    print_summary(summary)
    if not summary.training_guard_passed:
        raise SystemExit("training_guard_passed=false")


if __name__ == "__main__":
    main()
