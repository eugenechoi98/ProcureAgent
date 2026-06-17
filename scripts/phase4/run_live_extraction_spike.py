"""运行 Phase 4F 本地 OCR / LayoutLMv3 extraction spike。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.live_spike import (
    DEFAULT_CHECKPOINT,
    LiveExtractionFailure,
    run_live_extraction,
    write_failure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path, default=PROJECT_ROOT / DEFAULT_CHECKPOINT)
    parser.add_argument("--processor", type=Path)
    parser.add_argument("--label-map", type=Path)
    parser.add_argument("--disable-cpu", action="store_true")
    args = parser.parse_args()
    try:
        result = run_live_extraction(
            args.image,
            args.output_dir,
            checkpoint=args.checkpoint,
            processor=args.processor,
            label_map=args.label_map,
            cpu_allowed=not args.disable_cpu,
        )
    except LiveExtractionFailure as exc:
        result = write_failure(args.output_dir, exc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
