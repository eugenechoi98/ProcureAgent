"""运行 Phase 3K 离线 evidence citation baseline。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from procureguard.phase3.citation_evaluation import (
    evaluate_citation_challenge_set,
    load_citation_challenge_set,
)


def main() -> None:
    """生成 JSON 与 Markdown 审计报告。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/phase3k_citation_challenge_set.json"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/phase3/phase3k_evidence_citation_baseline.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("reports/phase3/phase3k_evidence_citation_baseline.md"))
    args = parser.parse_args()
    report = evaluate_citation_challenge_set(load_citation_challenge_set(args.fixture))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"baseline_passed": report["baseline_passed"], "citation_accept_reject_accuracy": report["citation_accept_reject_accuracy"], "fallback_accuracy": report["fallback_accuracy"], "accepted_only_metrics": report["accepted_only_metrics"], "all_candidate_metrics": report["all_candidate_metrics"]}, ensure_ascii=False, indent=2))


def _markdown(report: dict[str, Any]) -> str:
    """生成紧凑 Phase 3K 报告。"""

    lines = [
        "# Phase 3K Evidence Citation Baseline",
        "",
        "## 结论",
        "",
        f"- baseline：{'PASS' if report['baseline_passed'] else 'FAIL'}。",
        "- 本轮没有训练、没有加载模型、没有网络、没有 GPU、没有 live inference。",
        "- 本轮没有接 API，也没有修改 Phase 1、Phase 2、Demo 或 Docker。",
        "- deterministic template 仍是正式默认；citation-grounded structured explanation 只是离线实验。",
        "- LoRA 仍是 shadow / experimental / research。",
        "",
        "## 核心指标",
        "",
        f"- citation accept/reject accuracy：{report['citation_accept_reject_accuracy']:.4f}",
        f"- fallback accuracy：{report['fallback_accuracy']:.4f}",
        "",
        "### Accepted-only",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {key} | {value:.4f} |" for key, value in report["accepted_only_metrics"].items())
    lines.extend(["", "### All-candidate", "", "| metric | value |", "| --- | ---: |"])
    lines.extend(f"| {key} | {value:.4f} |" for key, value in report["all_candidate_metrics"].items())
    lines.extend([
        "",
        "所有候选指标包含故意构造的非法引用，因此用于观察挑战难度；是否通过以状态判断、拒绝原因、fallback 和 accepted-only 安全指标为准。",
        "",
        "## Challenge Set",
        "",
        f"共 {report['sample_count']} 条 synthetic test fixtures，不是真实企业数据，也不是训练数据。覆盖 PO 金额、GRN 缺失、重复检查、政策阈值、风险/动作正确引用，以及未知 ID、无关证据、金额/供应商错配、无依据审批人、风险/动作冲突、多异常漏引、无 citation、claim type 错配和缺失字段补全。",
        "",
        "## Reject Reasons",
        "",
        "```json",
        json.dumps(report["reject_reason_distribution"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 边界",
        "",
        "Evidence citation 提高了可追溯性，但不等于通用语义蕴含。当前 Claim-Evidence Validator 是保守规则，只覆盖声明类型、关键实体和稳定 evidence ID；它不能证明任意自然语言都被证据完整支持，也不能替代 Phase 3H Guard / Fallback。",
        "",
        "未运行真实模型 JSON 输出，没有使用或补造第二轮逐样本 artifacts。",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
