"""Phase 3D：只读诊断 CUDA runtime、Torch 和 bitsandbytes 训练环境。"""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.gpu_notebook import (  # noqa: E402
    cuda_runtime_diagnostics,
    notebook_kernel_python_from_env,
    notebook_model_dir_from_env,
)


def main() -> None:
    """输出 JSON 诊断，不安装依赖、不下载模型、不修改环境。"""

    parser = ArgumentParser()
    parser.add_argument("--model-dir")
    parser.add_argument("--expected-kernel-python")
    args = parser.parse_args()
    report = cuda_runtime_diagnostics(
        PROJECT_ROOT,
        model_dir=args.model_dir or notebook_model_dir_from_env(),
        expected_kernel_python=args.expected_kernel_python
        or notebook_kernel_python_from_env(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
