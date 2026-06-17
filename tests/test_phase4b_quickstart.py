"""Phase 4B clean-clone sample smoke 测试。"""

import json
from pathlib import Path

from scripts.samples.run_sample_audit import DEFAULT_INPUT, run_sample


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sample_audit_matches_documented_summary() -> None:
    """确认 synthetic sample 能稳定生成确定性 AuditReport。"""

    report = run_sample(DEFAULT_INPUT)
    expected = json.loads(
        (PROJECT_ROOT / "samples" / "expected_outputs" / "clean_invoice_summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["risk_level"] == expected["risk_level"]
    assert report["recommended_action"] == expected["recommended_action"]
    assert report["po_match"] is expected["po_match"]
    assert report["goods_receipt_match"] is expected["goods_receipt_match"]
    assert report["explanation"]["explanation_source"] == expected["explanation_source"]
    assert report["explanation"]["used_rewrite"] is False
