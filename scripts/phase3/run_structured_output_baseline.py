"""运行 Phase 3J 离线 structured-output baseline 并生成报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from procureguard.phase3.structured_evaluation import (
    evaluate_structured_challenge_set,
    load_challenge_set,
)


def main() -> None:
    """读取 challenge fixture，输出 JSON 与 Markdown 审计报告。"""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/phase3j_structured_challenge_set.json"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/phase3/phase3j_structured_output_baseline.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("reports/phase3/phase3j_structured_output_baseline.md"),
    )
    args = parser.parse_args()
    challenge_set = load_challenge_set(args.fixture)
    report = evaluate_structured_challenge_set(challenge_set)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    print(f"baseline_passed={report['baseline_passed']}")


def _render_markdown(report: dict[str, Any]) -> str:
    """生成面向审计的紧凑 Markdown 报告。"""

    metrics = report["metrics"]
    rows = [
        "# Phase 3J Structured Output First Baseline",
        "",
        "## 结论",
        "",
        f"- baseline 结果：{'PASS' if report['baseline_passed'] else 'FAIL'}。",
        "- 本轮没有训练模型、没有加载模型、没有 GPU、没有网络推理。",
        "- 本轮没有接 API，也没有修改 Phase 1、Phase 2、Demo 或 Docker。",
        "- deterministic template 仍是正式默认解释路径。",
        "- Structured Output First 只是离线实验；LoRA 仍是 shadow / experimental / research。",
        "",
        "## 指标摘要",
        "",
        "| metric | value |",
        "| --- | ---: |",
    ]
    rows.extend(f"| {key} | {value:.4f} |" for key, value in metrics.items())
    rows.extend(
        [
            "",
            "字段 precision / recall 统计包含 challenge set 中故意篡改的候选，因此低于 1 不代表 validator 放行错误。baseline 通过标准是预期状态与拒绝原因命中、fallback 正确，以及 accepted 输出的 unsupported claim 为 0。",
            "",
            "## Challenge Set",
            "",
            f"共 {report['sample_count']} 条 synthetic test fixtures，不是真实企业数据，也不是训练数据。",
            "覆盖未知 PO、未知 GRN、未知金额、无依据审批人、未知供应商、多异常漏项、冲突动作、冲突风险、同义但不完整表达、非法 evidence id、证据与 bullet 不匹配、异常类型新增和缺失字段篡改。",
            "",
            "## Reject Reason Distribution",
            "",
            "```json",
            json.dumps(report["reject_reason_distribution"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## 架构判断",
            "",
            "rule-only baseline 证明 schema、validator、renderer、evaluator 和 fallback 可以形成离线闭环。它不证明任何 LLM 已达到上线标准，也不改变 Phase 3H 的 Template / Guard / Fallback 架构。后续若实验模型 JSON 输出，仍必须复用同一 validator，并在任何失败时回退模板。",
            "",
            "## 未完成项",
            "",
            "- 未运行真实 base model JSON inference；按本轮边界仅完成 rule-only baseline。",
            "- 当前 evidence claim matching 是保守关键词校验，不是通用语义蕴含证明。",
            "- 没有使用或补造第二轮逐样本 artifacts。",
            "",
        ]
    )
    return "\n".join(rows)


if __name__ == "__main__":
    main()
