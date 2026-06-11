"""生成 Phase 3 synthetic 异常说明训练与评测数据。"""

from argparse import ArgumentParser
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.dataset import DEFAULT_SEED, write_dataset


def main() -> None:
    """解析 seed 并输出数据集摘要。"""

    parser = ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    summary = write_dataset(PROJECT_ROOT, seed=args.seed)
    print(
        f"generated={summary['sample_count']} "
        f"splits={summary['split_counts']} seed={summary['seed']}"
    )


if __name__ == "__main__":
    main()
