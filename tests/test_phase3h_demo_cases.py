"""Phase 3H 固定离线 Demo Cases 自动验证。"""

import json
from pathlib import Path

import pytest

from procureguard.phase3.explanation import (
    CanonicalAuditFacts,
    RewriteRequest,
    RewriteResponse,
    generate_guarded_explanation,
)

DEMO_PATH = Path(__file__).parent / "fixtures" / "phase3h_demo_cases.json"
DEMO_CASES = json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def _provider(behavior: str):
    """按固定行为返回 fake provider，不加载任何模型。"""

    if behavior == "none":
        return None

    def provider(request: RewriteRequest):
        if behavior == "pass":
            return RewriteResponse(
                raw_text=request.template_output,
                model_version="fake-demo-model",
                adapter_version="fake-demo-adapter",
            )
        if behavior == "guard_fail":
            invoice_number = request.facts.invoice_number
            return request.template_output.replace(
                invoice_number or "未提供（缺失）", "INV-UNSUPPORTED-999"
            )
        if behavior == "runtime_error":
            raise RuntimeError("fixed demo provider failure")
        if behavior == "invalid":
            return 123
        raise AssertionError(f"未知 provider_behavior: {behavior}")

    return provider


@pytest.mark.parametrize("case", DEMO_CASES, ids=lambda case: case["case_id"])
def test_phase3h_demo_case(case):
    facts = CanonicalAuditFacts.model_validate(case["facts"])

    result, metadata = generate_guarded_explanation(
        facts,
        mode=case["mode"],
        rewrite_provider=_provider(case["provider_behavior"]),
    )

    assert facts.risk_level == case["facts"]["risk_level"]
    assert facts.recommended_action == case["facts"]["recommended_action"]
    assert [item.value for item in facts.anomaly_types] == case["facts"]["anomaly_types"]
    assert metadata.explanation_source == case["expected_source"]
    assert metadata.fallback_reason == case["expected_fallback"]
    assert metadata.facts_hash == facts.facts_hash()
    assert metadata.anomaly_types == case["facts"]["anomaly_types"]
    assert result.explanation == metadata.explanation_text
    assert result.used_rewrite is (
        case["expected_source"] == "controlled_rewrite"
    )
