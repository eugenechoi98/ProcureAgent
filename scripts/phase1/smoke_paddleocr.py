"""PaddleOCR 端到端真实图片 smoke。"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.ocr import PaddleOCRAdapter


def main() -> None:
    """对少量图片运行 OCR，不输出完整票据文本。"""

    parser = argparse.ArgumentParser(description="Run PaddleOCR smoke on receipt images.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    image_paths = sorted(
        path
        for path in args.input.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    )[: args.limit]
    if not image_paths:
        raise SystemExit(f"No receipt images found in {args.input}.")

    try:
        adapter = PaddleOCRAdapter(lang="en")
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc
    for path in image_paths:
        tokens = adapter.extract_tokens(path)
        average = statistics.fmean(token.confidence for token in tokens) if tokens else 0.0
        print(
            f"sample_id={path.stem} token_count={len(tokens)} "
            f"average_confidence={average:.4f} "
            f"first_tokens={[token.text for token in tokens[:5]]}"
        )


if __name__ == "__main__":
    main()
