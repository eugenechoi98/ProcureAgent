"""只读检查 Phase 4F 本地 live extraction 资产。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.live_spike import DEFAULT_CHECKPOINT, check_live_extraction_assets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=PROJECT_ROOT / DEFAULT_CHECKPOINT)
    parser.add_argument("--processor", type=Path)
    parser.add_argument("--label-map", type=Path)
    parser.add_argument("--sample-image", type=Path)
    parser.add_argument("--disable-cpu", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = check_live_extraction_assets(
        args.checkpoint,
        processor=args.processor,
        label_map=args.label_map,
        sample_image=args.sample_image,
        cpu_allowed=not args.disable_cpu,
    )
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if summary["status"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
