"""用现有最佳 checkpoint 对比日期字段旧/新重建，不执行训练。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ["TOKENIZERS_PARALLELISM"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.gpu_notebook import require_safetensors_model
from procureguard.extraction.layoutlmv3_dataset import create_layoutlmv3_processor
from procureguard.extraction.phase1g_paths import resolve_image_root
from procureguard.extraction.validation_inference import (
    compare_reconstruction,
    predict_sample_labels,
    resolve_sample_images,
    write_comparison_outputs,
)


def main() -> None:
    """运行一次 validation inference 并输出实际 date F1 恢复幅度。"""

    parser = argparse.ArgumentParser(description="Compare date reconstruction using an existing checkpoint.")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument(
        "--image-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase1" / "checkpoint_inference",
    )
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()
    image_root = resolve_image_root(PROJECT_ROOT, explicit=args.image_root)

    require_safetensors_model(args.checkpoint)
    try:
        import torch
        from transformers import LayoutLMv3ForTokenClassification
    except ImportError as exc:
        raise SystemExit('Install Phase 1 dependencies with the current Kernel: pip install -e ".[extraction]"') from exc

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for the full 142-sample checkpoint inference.")
    samples = resolve_sample_images(
        read_processed_jsonl(args.validation),
        image_root,
    )
    processor = create_layoutlmv3_processor(args.checkpoint, local_files_only=True)
    device = torch.device("cuda")
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        args.checkpoint,
        local_files_only=True,
        use_safetensors=True,
    ).to(device)
    model.eval()
    predicted_labels = []
    for index, sample in enumerate(samples, start=1):
        predicted_labels.append(
            predict_sample_labels(
                sample,
                processor=processor,
                model=model,
                torch_module=torch,
                device=device,
                max_length=args.max_length,
            )
        )
        if index % 20 == 0 or index == len(samples):
            print(f"validation_progress={index}/{len(samples)}")
    report = compare_reconstruction(samples, predicted_labels)
    paths = write_comparison_outputs(report, args.output)
    print(f"legacy_date_f1={report['legacy_date_metric']['f1']:.6f}")
    print(f"cleaned_date_f1={report['cleaned_date_metric']['f1']:.6f}")
    print(f"date_f1_recovery={report['date_f1_recovery']:.6f}")
    print(f"recommendation={report['recommendation']}")
    print(f"outputs={paths}")


if __name__ == "__main__":
    main()
