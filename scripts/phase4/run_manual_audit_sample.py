"""运行 Phase 4C 手动审核 sample，不启动服务或访问网络。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from procureguard.productization import ManualAuditRequest, run_manual_audit
from procureguard.productization.manual_audit_store import (
    ManualAuditStore,
    ManualReviewDecisionRequest,
    render_export_json,
    render_export_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_ROOT / "samples" / "manual_audit"
CASES = {
    "standard_pass": SAMPLE_DIR / "request_standard_pass.json",
    "amount_mismatch": SAMPLE_DIR / "request_amount_mismatch.json",
    "missing_grn": SAMPLE_DIR / "request_missing_grn.json",
}
def run_case(
    path: Path,
    *,
    review_note: str | None = None,
    review_decision: str = "request_more_info",
    export_format: str | None = None,
    output_dir: Path | None = None,
) -> dict:
    """运行审核，可选附加 review 并导出文件。"""

    request = ManualAuditRequest.model_validate_json(path.read_text(encoding="utf-8"))
    response = run_manual_audit(request)
    store = ManualAuditStore()
    record = store.save(request, response)
    if review_note is not None:
        record = store.submit_review(
            response.audit_id,
            ManualReviewDecisionRequest(
                decision=review_decision,
                reviewer_note=review_note,
            ),
        )
    export_path = None
    if export_format:
        rendered = (
            render_export_json(record)
            if export_format == "json"
            else render_export_markdown(record)
        )
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            suffix = "json" if export_format == "json" else "md"
            export_path = output_dir / f"{path.stem}.{suffix}"
            export_path.write_text(rendered, encoding="utf-8")
    return {
        "response": response.model_dump(mode="json"),
        "review": record.review.model_dump(mode="json"),
        "export_format": export_format,
        "export_path": str(export_path) if export_path else None,
    }


def main() -> int:
    """运行单个或全部内置场景并输出 JSON。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASES, "all"], default="all")
    parser.add_argument("--review", help="Reviewer note for a case that requires human review.")
    parser.add_argument(
        "--decision",
        choices=["approve", "reject", "request_more_info"],
        default="request_more_info",
    )
    parser.add_argument("--export", choices=["json", "markdown"])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    if args.case == "all" and args.review:
        parser.error("--review requires a single --case")

    selected = CASES if args.case == "all" else {args.case: CASES[args.case]}
    try:
        results = {
            name: run_case(
                path,
                review_note=args.review,
                review_decision=args.decision,
                export_format=args.export,
                output_dir=args.output_dir.resolve() if args.output_dir else None,
            )
            for name, path in selected.items()
        }
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Manual audit sample failed: {exc}", file=sys.stderr)
        return 1

    payload = results if args.case == "all" else results[args.case]
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
