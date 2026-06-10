"""LayoutLMv3 单 batch forward smoke，不进行长时间训练。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.alignment import ID2LABEL, LABEL2ID
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.layoutlmv3_dataset import SROIELayoutLMv3Dataset, create_layoutlmv3_processor


def main() -> None:
    """加载 microsoft/layoutlmv3-base 并只跑一个 batch。"""

    parser = argparse.ArgumentParser(description="Smoke test one LayoutLMv3 forward batch.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    try:
        import torch
        from torch.utils.data import DataLoader
        from transformers import LayoutLMv3ForTokenClassification
    except ImportError as exc:
        raise SystemExit('Missing torch/transformers. Run: .\\.venv\\Scripts\\python.exe -m pip install -e ".[extraction]"') from exc

    processor = create_layoutlmv3_processor()
    samples = read_processed_jsonl(args.input)
    dataset = SROIELayoutLMv3Dataset(samples, processor, LABEL2ID, max_length=args.max_length)
    batch = next(iter(DataLoader(dataset, batch_size=args.batch_size)))
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        "microsoft/layoutlmv3-base",
        num_labels=len(LABEL2ID),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    batch = {key: value.to(device) for key, value in batch.items()}
    model.eval()
    with torch.no_grad():
        outputs = model(**batch)
    labels = batch["labels"]
    print(f"device={device}")
    print(f"loss={float(outputs.loss):.6f}")
    print(f"logits_shape={tuple(outputs.logits.shape)}")
    print(f"labels_non_o_count={int(((labels != -100) & (labels != LABEL2ID['O'])).sum().item())}")


if __name__ == "__main__":
    main()
