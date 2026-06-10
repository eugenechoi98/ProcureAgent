"""手动执行真实 PaddleOCR + Regex baseline 的 smoke 脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.baseline import SroieRegexBaseline
from procureguard.extraction.ocr import PaddleOCRAdapter


def main() -> None:
    """读取图片，输出 SROIE baseline JSON。"""

    parser = argparse.ArgumentParser(description="Run PaddleOCR + SROIE regex baseline.")
    parser.add_argument("image_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    tokens = PaddleOCRAdapter(lang="en").extract_tokens(args.image_path)
    extracted = SroieRegexBaseline().extract(tokens)
    payload = {
        "baseline_name": extracted.baseline_name,
        "fields": {name: field.__dict__ for name, field in extracted.fields.items()},
        "procureguard_mapping": extracted.to_procureguard_fields(),
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
