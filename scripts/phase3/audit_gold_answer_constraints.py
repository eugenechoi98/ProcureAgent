"""审查 Phase 3F gold answer 的事实约束与数据 diff。"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.dataset import ANOMALY_LABELS, ANSWER_SECTIONS, SPLITS  # noqa: E402
from procureguard.phase3.evaluation import evaluate_explanation, load_samples  # noqa: E402


DATA_FILES = tuple(f"data/phase3/generated/{split}.jsonl" for split in SPLITS)
REQUIRED_REPORT_KEYS = ("constraint_audit", "dataset_diff")


def sha256_file(path: Path) -> str:
    """计算文件 SHA-256。"""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL。"""

    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def git_show_text(ref: str, relative_path: str) -> str | None:
    """读取 Git ref 中的旧文件内容。"""

    result = subprocess.run(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout if result.returncode == 0 else None


def sample_shape(row: dict[str, Any]) -> dict[str, Any]:
    """提取不会泄露长文本的样本摘要。"""

    return {
        "sample_id": row["sample_id"],
        "split": row["split"],
        "anomaly_type": row["anomaly_type"],
        "included_anomaly_types": row["metadata"]["included_anomaly_types"],
        "expected_explanation_sha256": hashlib.sha256(
            row["expected_explanation"].encode("utf-8")
        ).hexdigest(),
        "expected_explanation_lines": row["expected_explanation"].count("\n") + 1,
    }


def dataset_diff(base_ref: str) -> dict[str, Any]:
    """生成当前数据与 Git ref 中旧数据的摘要 diff。"""

    files: dict[str, Any] = {}
    changed_samples = 0
    unchanged_input_facts = 0
    for relative in DATA_FILES:
        current_path = PROJECT_ROOT / relative
        current_rows = read_jsonl(current_path)
        previous_text = git_show_text(base_ref, relative)
        previous_rows = [
            json.loads(line) for line in previous_text.splitlines() if line.strip()
        ] if previous_text else []
        previous_by_id = {row["sample_id"]: row for row in previous_rows}
        changed_ids: list[str] = []
        for row in current_rows:
            previous = previous_by_id.get(row["sample_id"])
            if previous is None:
                changed_ids.append(row["sample_id"])
                continue
            if previous.get("expected_explanation") != row.get("expected_explanation"):
                changed_ids.append(row["sample_id"])
                if previous.get("input_facts") == row.get("input_facts"):
                    unchanged_input_facts += 1
        changed_samples += len(changed_ids)
        files[relative] = {
            "previous_exists": previous_text is not None,
            "previous_count": len(previous_rows),
            "current_count": len(current_rows),
            "current_sha256": sha256_file(current_path),
            "changed_expected_explanation_count": len(changed_ids),
            "changed_expected_explanation_sample_ids": changed_ids[:10],
            "first_current_sample": sample_shape(current_rows[0]) if current_rows else None,
        }
    return {
        "base_ref": base_ref,
        "files": files,
        "changed_expected_explanation_total": changed_samples,
        "unchanged_input_facts_for_changed_answers": unchanged_input_facts,
    }


def label_violations(row: dict[str, Any]) -> list[str]:
    """检查多异常回答是否包含未输入异常标签。"""

    explanation = row["expected_explanation"]
    allowed = set(row["input_facts"]["anomaly_types"])
    violations: list[str] = []
    for anomaly_type, label in ANOMALY_LABELS.items():
        if anomaly_type.value not in allowed and label in explanation:
            violations.append(anomaly_type.value)
    return violations


def audit_row(row: dict[str, Any]) -> list[str]:
    """审查单条 gold answer 的事实约束。"""

    failures: list[str] = []
    explanation = row["expected_explanation"]
    facts = row["input_facts"]
    if not all(section in explanation for section in ANSWER_SECTIONS):
        failures.append("missing_required_sections")
    if facts.get("po_number") is None and not (
        "采购订单号：未提供" in explanation and "缺失" in explanation
    ):
        failures.append("missing_po_not_marked")
    if facts.get("grn_number") is None and not (
        "收货单号：未提供" in explanation and "缺失" in explanation
    ):
        failures.append("missing_grn_not_marked")
    if facts.get("po_number") is None and "不得根据发票号推断采购订单号" not in explanation:
        failures.append("missing_po_completion_ban")
    if facts.get("grn_number") is None and "不得根据发票号推断收货单号" not in explanation:
        failures.append("missing_grn_completion_ban")
    if "没有金额不一致证据时不得生成金额对比" not in explanation and all(
        item.get("field") != "total_amount" for item in facts.get("mismatches", [])
    ):
        failures.append("missing_amount_completion_ban")
    if "没有供应商不一致证据时不得生成供应商不匹配" not in explanation and all(
        item.get("field") != "vendor_name" for item in facts.get("mismatches", [])
    ):
        failures.append("missing_vendor_completion_ban")
    if label_violations(row):
        failures.append("mentions_unprovided_anomaly_type")
    return failures


def constraint_audit() -> dict[str, Any]:
    """审查所有 split 的 gold answer。"""

    failure_counts: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    metrics_failures: list[str] = []
    split_counts: Counter[str] = Counter()
    section_shapes: Counter[str] = Counter()
    for relative in DATA_FILES:
        path = PROJECT_ROOT / relative
        rows = read_jsonl(path)
        samples = load_samples(path)
        by_id = {sample.sample_id: sample for sample in samples}
        for row in rows:
            split_counts[row["split"]] += 1
            section_shapes[
                "|".join(line.split("：", 1)[0] for line in row["expected_explanation"].splitlines())
            ] += 1
            row_failures = audit_row(row)
            if row_failures:
                failure_counts.update(row_failures)
                failures.append({"sample_id": row["sample_id"], "failures": row_failures})
            result = evaluate_explanation(by_id[row["sample_id"]], row["expected_explanation"])
            if not (
                result["format_compliance"]
                and result["factual_consistency"]
                and result["action_consistency"]
                and result["anomaly_coverage"] == 1.0
                and not result["hallucination"]
            ):
                metrics_failures.append(row["sample_id"])
    return {
        "ok": not failures and not metrics_failures,
        "split_counts": dict(sorted(split_counts.items())),
        "section_shapes": dict(sorted(section_shapes.items())),
        "failure_counts": dict(sorted(failure_counts.items())),
        "failure_samples": failures[:20],
        "metric_failure_sample_ids": metrics_failures[:20],
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """导出 Markdown 审查报告。"""

    audit = report["constraint_audit"]
    diff = report["dataset_diff"]
    lines = [
        "# Phase 3F Gold Answer Constraint Audit",
        "",
        f"- constraint_ok: `{str(audit['ok']).lower()}`",
        f"- changed_expected_explanation_total: `{diff['changed_expected_explanation_total']}`",
        f"- unchanged_input_facts_for_changed_answers: `{diff['unchanged_input_facts_for_changed_answers']}`",
        "",
        "## Split Counts",
        "",
        "| split | count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in audit["split_counts"].items())
    lines.extend(["", "## Current File SHA-256", ""])
    for relative, item in diff["files"].items():
        lines.append(f"- `{relative}`: `{item['current_sha256']}`")
    lines.extend(["", "## Section Shapes", "", "```json"])
    lines.append(json.dumps(audit["section_shapes"], ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Failure Counts", "", "```json"])
    lines.append(json.dumps(audit["failure_counts"], ensure_ascii=False, indent=2))
    lines.extend(["```", ""])
    return "\n".join(lines)


def diff_to_markdown(diff: dict[str, Any]) -> str:
    """导出独立数据 diff 报告。"""

    lines = [
        "# Phase 3F Dataset Diff",
        "",
        f"- base_ref: `{diff['base_ref']}`",
        f"- changed_expected_explanation_total: `{diff['changed_expected_explanation_total']}`",
        f"- unchanged_input_facts_for_changed_answers: `{diff['unchanged_input_facts_for_changed_answers']}`",
        "",
        "| file | previous count | current count | changed answers | current sha256 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for relative, item in diff["files"].items():
        lines.append(
            f"| `{relative}` | {item['previous_count']} | {item['current_count']} | "
            f"{item['changed_expected_explanation_count']} | `{item['current_sha256']}` |"
        )
    lines.extend(["", "## First Changed Sample Per File", ""])
    for relative, item in diff["files"].items():
        lines.append(f"### {relative}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(item["first_current_sample"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """CLI 入口。"""

    parser = ArgumentParser()
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3f_constraint_audit.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3f_constraint_audit.md",
    )
    parser.add_argument(
        "--diff-json",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3f_dataset_diff.json",
    )
    parser.add_argument(
        "--diff-md",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3f_dataset_diff.md",
    )
    args = parser.parse_args()
    report = {
        "constraint_audit": constraint_audit(),
        "dataset_diff": dataset_diff(args.base_ref),
    }
    if not all(key in report for key in REQUIRED_REPORT_KEYS):
        raise RuntimeError("internal report shape is invalid")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output_md.write_text(report_to_markdown(report), encoding="utf-8", newline="\n")
    args.diff_json.write_text(
        json.dumps(report["dataset_diff"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.diff_md.write_text(diff_to_markdown(report["dataset_diff"]), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": report["constraint_audit"]["ok"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
