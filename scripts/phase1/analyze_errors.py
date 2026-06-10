"""从 baseline report 输出错误分析 Markdown 或 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.error_analysis import errors_to_markdown


def main() -> None:
    """读取评测报告并输出错误案例。"""

    parser = argparse.ArgumentParser(description="Write baseline error analysis.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    errors = report.get("errors", [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() == ".json":
        args.output.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        args.output.write_text(errors_to_markdown([SimpleError(error) for error in errors]), encoding="utf-8")
    print(f"errors={len(errors)} output={args.output}")


class SimpleError:
    """把报告里的 dict 包成 errors_to_markdown 需要的属性对象。"""

    def __init__(self, payload: dict[str, object]):
        self.sample_id = str(payload.get("sample_id", ""))
        self.field = str(payload.get("field", ""))
        self.predicted = payload.get("predicted")
        self.ground_truth = payload.get("ground_truth")
        self.error_type = str(payload.get("error_type", "unknown"))
        self.notes = str(payload.get("notes", ""))


if __name__ == "__main__":
    main()
