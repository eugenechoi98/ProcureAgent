"""LayoutLMv3 Dataset/DataLoader 单 batch smoke。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.alignment import LABEL2ID
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.layoutlmv3_dataset import SROIELayoutLMv3Dataset, create_layoutlmv3_processor


def main() -> None:
    """构造一个 DataLoader batch 并输出 shape。"""

    parser = argparse.ArgumentParser(description="Smoke test LayoutLMv3 DataLoader batch.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    try:
        from torch.utils.data import DataLoader
    except ImportError as exc:
        raise SystemExit('Torch is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -e ".[extraction]"') from exc

    try:
        processor = create_layoutlmv3_processor()
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    samples = read_processed_jsonl(args.input)
    dataset = SROIELayoutLMv3Dataset(samples, processor, LABEL2ID, max_length=args.max_length)
    batch = next(iter(DataLoader(dataset, batch_size=args.batch_size)))
    print(f"batch_keys={list(batch.keys())}")
    for key, value in batch.items():
        print(f"{key}_shape={tuple(value.shape)}")
    labels = batch["labels"]
    print(f"labels_non_ignore_count={int((labels != -100).sum().item())}")


if __name__ == "__main__":
    main()
