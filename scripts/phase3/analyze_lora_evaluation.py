"""离线复盘 Phase 3 首轮 LoRA 真实评测结果。"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.phase3.evaluation import (  # noqa: E402
    aggregate_results,
    evaluate_explanation,
    load_predictions,
    load_samples,
)
from procureguard.phase3.runtime import GenerationConfig, SYSTEM_PROMPT  # noqa: E402


METRIC_KEYS = (
    "format_compliance",
    "factual_consistency",
    "action_consistency",
    "anomaly_coverage",
    "hallucination_rate",
)
FORMAT_COMPONENT_LABELS = {
    "required_sections": "missing_fixed_sections",
    "anomaly_type_present": "missing_anomaly_type",
    "critical_facts_present": "missing_critical_facts",
    "recommended_action_present": "missing_recommended_action",
    "risk_level_present": "missing_risk_level",
}
REQUIRED_ARTIFACTS = (
    "predictions/base.jsonl",
    "predictions/fine_tuned.jsonl",
    "evaluation/evaluation.json",
    "evaluation/evaluation.md",
    "logs/training_config.json",
    "logs/trainer_log_history.json",
)


def require_files(paths: list[Path]) -> None:
    """确认真实云端产物已同步到本地。"""

    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Phase 3E review requires real ModelScope artifacts. Missing files: "
            + ", ".join(missing)
            + ". Copy the cloud artifacts to a local directory such as "
            "D:/ProcureAgentArtifacts/phase3 and pass --artifacts-dir."
        )


def evaluation_rows(samples: list[Any], predictions: dict[str, str]) -> list[dict[str, Any]]:
    """重新按当前 rubric 计算逐样本评测结果。"""

    missing = [sample.sample_id for sample in samples if sample.sample_id not in predictions]
    if missing:
        raise ValueError(f"missing predictions for {len(missing)} samples: {missing[:3]}")
    return [
        evaluate_explanation(sample, predictions[sample.sample_id])
        | {
            "anomaly_type": sample.anomaly_type.value,
            "input_facts": sample.input_facts.model_dump(mode="json"),
            "model_output": predictions[sample.sample_id],
        }
        for sample in samples
    ]


def aggregate_by_anomaly_type(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按 anomaly_type 汇总五个核心指标。"""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["anomaly_type"]].append(row)
    return {
        anomaly_type: aggregate_results(items)
        for anomaly_type, items in sorted(grouped.items())
    }


def classify_hallucination(sample: dict[str, Any], violation: str) -> str:
    """把 hallucination violation 归到便于复盘的根因类别。"""

    anomaly_type = sample["anomaly_type"]
    if violation.startswith("unknown_amount"):
        return "amount_fact_not_constrained"
    if violation.startswith("unknown_identifier:GRN") and anomaly_type == "missing_goods_receipt":
        return "missing_grn_filled_by_pattern"
    if violation.startswith("unknown_identifier"):
        return "identifier_filled_by_pattern"
    if violation.startswith("unknown_vendor"):
        return "vendor_relation_overgeneralized"
    if violation.startswith("unsupported_policy_or_approver"):
        return "unsupported_policy_or_approver"
    return "unknown_fact_added"


def hallucination_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """列出全部 hallucination 样本和 violation。"""

    items: list[dict[str, Any]] = []
    for row in rows:
        for violation in row["hallucination_violations"]:
            items.append(
                {
                    "sample_id": row["sample_id"],
                    "anomaly_type": row["anomaly_type"],
                    "input_facts": row["input_facts"],
                    "model_output": row["model_output"],
                    "violation": violation,
                    "root_cause": classify_hallucination(row, violation),
                }
            )
    return items


def format_failure_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    """统计 format_compliance 失败的组成原因。"""

    counts: Counter[str] = Counter()
    for row in rows:
        if row["format_compliance"]:
            continue
        for key, ok in row["format_components"].items():
            if not ok:
                counts[FORMAT_COMPONENT_LABELS.get(key, key)] += 1
    return dict(sorted(counts.items()))


def dataset_diagnostics(dataset_rows: list[Any]) -> dict[str, Any]:
    """检查训练/验证/测试数据的模板和约束表达风险。"""

    section_shapes = Counter()
    anomaly_counts = Counter()
    multi_issue_count = 0
    missing_constraint_terms = Counter()
    for sample in dataset_rows:
        text = sample.expected_explanation
        anomaly_counts[sample.anomaly_type.value] += 1
        if sample.anomaly_type.value == "multi_issue_combination":
            multi_issue_count += 1
        section_shapes[tuple(line.split("：", 1)[0] for line in text.splitlines())] += 1
        if "不得" not in text and "只能" not in text:
            missing_constraint_terms["no_negative_constraint_in_answer"] += 1
        if "未提供" not in text and "缺失" not in text and (
            sample.input_facts.po_number is None or sample.input_facts.grn_number is None
        ):
            missing_constraint_terms["missing_field_not_explicitly_marked"] += 1
    return {
        "sample_count": len(dataset_rows),
        "anomaly_type_counts": dict(sorted(anomaly_counts.items())),
        "multi_issue_count": multi_issue_count,
        "section_shape_counts": {str(key): value for key, value in section_shapes.items()},
        "risk_flags": dict(sorted(missing_constraint_terms.items())),
    }


def prompt_diagnostics() -> dict[str, bool]:
    """检查当前 system prompt 是否覆盖事实约束。"""

    return {
        "only_reference_input_facts": "只能复述输入事实" in SYSTEM_PROMPT,
        "forbid_unknown_amounts_identifiers_vendors": all(
            term in SYSTEM_PROMPT for term in ("单号", "金额", "业务事实")
        ),
        "forbid_change_risk_level_or_action": "改变风险等级或建议动作" in SYSTEM_PROMPT,
        "requires_fixed_sections": all(
            section in SYSTEM_PROMPT for section in ("异常类型", "关键事实", "审核结论")
        ),
        "requires_missing_fields_literal": "缺失" in SYSTEM_PROMPT or "未提供" in SYSTEM_PROMPT,
    }


def generation_diagnostics(training_config: dict[str, Any]) -> dict[str, Any]:
    """检查生成参数是否存在无效采样参数。"""

    generation = training_config.get("generation", {})
    defaults = GenerationConfig()
    do_sample = generation.get("do_sample", defaults.do_sample)
    inactive_sampling_keys = [
        key for key in ("temperature", "top_p", "top_k") if key in generation and do_sample is False
    ]
    return {
        "generation": generation or {
            "max_new_tokens": defaults.max_new_tokens,
            "do_sample": defaults.do_sample,
        },
        "inactive_sampling_keys": inactive_sampling_keys,
        "recommendation": "remove inactive temperature/top_p/top_k when do_sample=false"
        if inactive_sampling_keys
        else "no inactive sampling keys found",
    }


def build_report(
    *,
    project_root: Path,
    artifacts_dir: Path,
    dataset_path: Path,
    train_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    """生成 Phase 3E 复盘 JSON。"""

    artifact_paths = [artifacts_dir / relative for relative in REQUIRED_ARTIFACTS]
    require_files([dataset_path, train_path, validation_path, *artifact_paths])

    samples = load_samples(dataset_path)
    train_rows = load_samples(train_path)
    validation_rows = load_samples(validation_path)
    base_rows = evaluation_rows(samples, load_predictions(artifacts_dir / "predictions" / "base.jsonl"))
    fine_tuned_rows = evaluation_rows(
        samples,
        load_predictions(artifacts_dir / "predictions" / "fine_tuned.jsonl"),
    )
    training_config = json.loads(
        (artifacts_dir / "logs" / "training_config.json").read_text(encoding="utf-8")
    )
    evaluation_json = json.loads(
        (artifacts_dir / "evaluation" / "evaluation.json").read_text(encoding="utf-8")
    )
    return {
        "project_root": str(project_root),
        "artifacts_dir": str(artifacts_dir),
        "source_evaluation_metrics": {
            name: report["metrics"] for name, report in evaluation_json.items()
        },
        "by_anomaly_type": {
            "base": aggregate_by_anomaly_type(base_rows),
            "fine_tuned": aggregate_by_anomaly_type(fine_tuned_rows),
        },
        "hallucinations": {
            "base": hallucination_rows(base_rows),
            "fine_tuned": hallucination_rows(fine_tuned_rows),
        },
        "format_failure_distribution": {
            "base": format_failure_distribution(base_rows),
            "fine_tuned": format_failure_distribution(fine_tuned_rows),
        },
        "dataset_diagnostics": {
            "train": dataset_diagnostics(train_rows),
            "validation": dataset_diagnostics(validation_rows),
            "test": dataset_diagnostics(samples),
        },
        "prompt_diagnostics": prompt_diagnostics(),
        "generation_diagnostics": generation_diagnostics(training_config),
        "single_variable_recommendation": {
            "variable": "fact_constrained_prompt_and_uniform_expected_explanation_format",
            "reason": (
                "The first run improved action and anomaly coverage, but hallucination and "
                "format failures show the model learned the task intent before learning hard "
                "fact boundaries."
            ),
            "expected_improvements": [
                "format_compliance",
                "factual_consistency",
                "hallucination_rate",
                "anomaly_coverage",
            ],
        },
        "hard_gates": {
            "factual_consistency": 0.95,
            "hallucination_rate_max": 0.05,
            "action_consistency": 0.90,
            "anomaly_coverage": 0.90,
            "format_compliance": 0.90,
        },
    }


def markdown_table_by_type(report: dict[str, Any]) -> list[str]:
    """输出按异常类型拆分的指标表。"""

    lines = [
        "## By Anomaly Type",
        "",
        "| model | anomaly_type | samples | format | factual | action | anomaly coverage | hallucination rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model_name in ("base", "fine_tuned"):
        for anomaly_type, metrics in report["by_anomaly_type"][model_name].items():
            lines.append(
                f"| {model_name} | {anomaly_type} | {metrics['sample_count']} | "
                f"{metrics['format_compliance']:.4f} | {metrics['factual_consistency']:.4f} | "
                f"{metrics['action_consistency']:.4f} | {metrics['anomaly_coverage']:.4f} | "
                f"{metrics['hallucination_rate']:.4f} |"
            )
    return lines


def report_to_markdown(report: dict[str, Any]) -> str:
    """把 Phase 3E 复盘结果导出为 Markdown。"""

    lines = ["# Phase 3E First LoRA Evaluation Review", ""]
    lines.extend(markdown_table_by_type(report))
    lines.extend(["", "## Hallucinations", ""])
    for model_name in ("base", "fine_tuned"):
        lines.append(f"### {model_name}")
        rows = report["hallucinations"][model_name]
        if not rows:
            lines.append("- none")
        for item in rows:
            lines.append(
                f"- `{item['sample_id']}` `{item['anomaly_type']}` "
                f"{item['violation']} -> {item['root_cause']}"
            )
        lines.append("")
    lines.extend(["## Format Failure Distribution", ""])
    lines.append("```json")
    lines.append(json.dumps(report["format_failure_distribution"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.extend(["", "## Dataset Diagnostics", ""])
    lines.append("```json")
    lines.append(json.dumps(report["dataset_diagnostics"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.extend(["", "## Prompt Diagnostics", ""])
    lines.append("```json")
    lines.append(json.dumps(report["prompt_diagnostics"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.extend(["", "## Generation Diagnostics", ""])
    lines.append("```json")
    lines.append(json.dumps(report["generation_diagnostics"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.extend(["", "## Recommendation", ""])
    lines.append(json.dumps(report["single_variable_recommendation"], ensure_ascii=False, indent=2))
    lines.extend(["", "## Hard Gates", ""])
    lines.append(json.dumps(report["hard_gates"], ensure_ascii=False, indent=2))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """CLI 入口。"""

    parser = ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--artifacts-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "phase3")
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "data" / "phase3" / "generated" / "test.jsonl")
    parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data" / "phase3" / "generated" / "train.jsonl")
    parser.add_argument(
        "--validation",
        type=Path,
        default=PROJECT_ROOT / "data" / "phase3" / "generated" / "validation.jsonl",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3e_lora_review.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=PROJECT_ROOT / "reports" / "phase3" / "phase3e_lora_review.md",
    )
    args = parser.parse_args()

    report = build_report(
        project_root=args.project_root.resolve(),
        artifacts_dir=args.artifacts_dir.resolve(),
        dataset_path=args.dataset.resolve(),
        train_path=args.train.resolve(),
        validation_path=args.validation.resolve(),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output_md.write_text(report_to_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"output_json": str(args.output_json), "output_md": str(args.output_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
