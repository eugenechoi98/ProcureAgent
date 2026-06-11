"""首轮 GPU 结果、日期诊断和 hybrid 离线评测工具。"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Iterable

from procureguard.extraction.alignment import align_sample_tokens, normalize_for_alignment
from procureguard.extraction.baseline import SroieRegexBaseline, normalize_date
from procureguard.extraction.field_reconstruction import reconstruct_bio_fields
from procureguard.extraction.metrics import FieldMetric
from procureguard.extraction.schemas import SroieSample
from procureguard.extraction.training import (
    EpochLog,
    LayoutLMv3TrainingConfig,
    build_training_report,
    save_loss_curve,
    write_training_outputs,
)


FIRST_GPU_FIELD_METRICS = [
    FieldMetric("company", 0.822429906542056, 0.6197183098591549, 0.7068273092369478, 142, 88, 19, 54),
    FieldMetric("address", 0.7428571428571429, 0.7323943661971831, 0.7375886524822696, 142, 104, 36, 38),
    FieldMetric("date", 0.152, 0.13380281690140844, 0.14232209737827717, 142, 19, 106, 123),
    FieldMetric("total", 0.9328358208955224, 0.8802816901408451, 0.9057971014492754, 142, 125, 9, 17),
]
FIRST_GPU_EPOCH_LOGS = [
    EpochLog(1, 0.7666405623419243, 0.1868693458152489, 0.612942612942613, 0.2727845398248986, 8.888888888888888e-06, 127.64075681194663),
    EpochLog(2, 0.13186411524289532, 0.08232416700519307, 0.820763956904995, 0.5673369395358037, 6.666666666666667e-06, 117.57254588231444),
    EpochLog(3, 0.07848083919012233, 0.06808421690620377, 0.846081208687441, 0.5987341826702939, 4.444444444444444e-06, 117.68678881041706),
    EpochLog(4, 0.0615527684457208, 0.06136300898826038, 0.8538899430740038, 0.6071122566464308, 2.222222222222222e-06, 118.3314143884927),
    EpochLog(5, 0.052901825828379705, 0.059224570878374745, 0.8647114474929044, 0.6231337901366925, 0.0, 118.65647425316274),
]
BASELINE_F1 = {
    "company": 0.5704225352112676,
    "address": 0.007042253521126761,
    "date": 0.8292682926829269,
    "total": 0.34814814814814815,
    "macro": 0.43872030739086737,
}
DATE_PATTERN = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})\b"
)


def normalize_analysis_date(value: str) -> str:
    """日期分析额外识别 YYYYMMDD，不改变既有 Regex baseline。"""

    normalized = normalize_date(value)
    if normalized:
        return normalized
    if re.fullmatch(r"\d{8}", value.strip()):
        text = value.strip()
        candidate = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        return normalize_date(candidate)
    return ""


def first_gpu_training_report() -> dict[str, object]:
    """生成用户已确认的首轮 GPU 训练报告。"""

    report = build_training_report(
        config=LayoutLMv3TrainingConfig(),
        logs=FIRST_GPU_EPOCH_LOGS,
        baseline_macro_f1=BASELINE_F1["macro"],
    )
    report.update(
        {
            "run_name": "first_gpu_fine_tuning_run",
            "result_source": "user_confirmed_modelscope_gpu_run",
            "gpu": "NVIDIA A10",
            "checkpoint_path": "checkpoints/phase1/layoutlmv3_best",
            "evaluation_split": "local_validation_split_seed_42",
            "official_test": False,
            "field_metrics": [asdict(metric) for metric in FIRST_GPU_FIELD_METRICS],
        }
    )
    return report


def write_first_gpu_outputs(output_dir: str | Path) -> dict[str, Path]:
    """固化 JSON、CSV、Markdown 和真实 epoch loss 曲线。"""

    report = first_gpu_training_report()
    paths = write_training_outputs(report, output_dir)
    markdown = paths["markdown"].read_text(encoding="utf-8")
    markdown = markdown.replace(
        "# LayoutLMv3 Training Report\n",
        "# First GPU Fine-tuning Run\n\n"
        "- gpu: NVIDIA A10\n"
        "- result_source: user_confirmed_modelscope_gpu_run\n"
        "- official_test: false\n",
        1,
    )
    field_lines = [
        "",
        "## Field Metrics",
        "",
        "| field | precision | recall | f1 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in report["field_metrics"]:
        field_lines.append(
            f"| {metric['field']} | {metric['precision']:.4f} | "
            f"{metric['recall']:.4f} | {metric['f1']:.4f} |"
        )
    paths["markdown"].write_text(markdown + "\n".join(field_lines) + "\n", encoding="utf-8")
    paths["loss_curve"] = save_loss_curve(
        FIRST_GPU_EPOCH_LOGS,
        Path(output_dir) / "layoutlmv3_loss_curve.png",
    )
    return paths


def date_format(value: str) -> str:
    """粗分 ground truth 或预测日期格式。"""

    text = value.strip()
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", text):
        return "DD-MM-YYYY"
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", text):
        return "DD/MM/YYYY"
    if re.fullmatch(r"\d{1,2}[-/]\d{1,2}[-/]\d{2}", text):
        return "DD/MM/YY_or_DD-MM-YY"
    if re.search(r"[A-Za-z]", text):
        return "text_month"
    return "other"


def date_candidates(sample: SroieSample) -> list[str]:
    """从 OCR token 中提取日期候选。"""

    candidates: list[str] = []
    for token in sample.tokens:
        candidates.extend(match.group(0) for match in DATE_PATTERN.finditer(token.text))
    return candidates


def reconstruct_gold_date(sample: SroieSample, labels: list[str]) -> str:
    """按 Notebook reconstruction 规则从金标 BIO 恢复日期。"""

    parts: list[str] = []
    active = False
    for token, label in zip(sample.tokens, labels, strict=True):
        if label == "B-DATE":
            parts = [token.text]
            active = True
        elif label == "I-DATE" and active:
            parts.append(token.text)
        elif active:
            break
    return " ".join(parts).strip()


def analyze_date_validation(samples: list[SroieSample]) -> dict[str, object]:
    """分析不依赖模型预测即可验证的日期数据、OCR、alignment 和重建证据。"""

    formats: Counter[str] = Counter()
    evidence = Counter()
    cases: dict[str, list[dict[str, object]]] = {
        "ocr_missing": [],
        "alignment_miss": [],
        "multiple_date_candidates": [],
        "field_reconstruction_error": [],
        "field_reconstruction_error_after_cleanup": [],
        "truncation": [],
    }
    for sample in samples:
        ground_truth = sample.labels["date"]
        formats[date_format(ground_truth)] += 1
        canonical_target = normalize_analysis_date(ground_truth)
        raw_target = normalize_for_alignment(ground_truth)
        candidates = date_candidates(sample)
        canonical_candidates = [normalize_analysis_date(candidate) for candidate in candidates]
        raw_ocr = "".join(normalize_for_alignment(token.text) for token in sample.tokens)
        labels, unaligned = align_sample_tokens(sample)
        reconstructed = reconstruct_gold_date(sample, labels)
        cleaned_reconstructed = reconstruct_bio_fields(sample.tokens, labels)["date"]
        normalized_target = canonical_target or normalize_for_alignment(ground_truth, "date")
        normalized_reconstructed = normalize_date(reconstructed) or normalize_for_alignment(reconstructed, "date")
        normalized_cleaned = normalize_date(cleaned_reconstructed) or normalize_for_alignment(cleaned_reconstructed, "date")
        case = {
            "sample_id": sample.sample_id,
            "ground_truth": ground_truth,
            "date_candidates": candidates,
            "token_count": len(sample.tokens),
            "reconstructed": reconstructed,
            "cleaned_reconstructed": cleaned_reconstructed,
        }
        ocr_contains_target = (
            bool(canonical_target and canonical_target in canonical_candidates)
            or bool(raw_target and raw_target in raw_ocr)
        )
        if not ocr_contains_target:
            evidence["ocr_missing"] += 1
            cases["ocr_missing"].append(case)
        if any(item.field == "date" for item in unaligned):
            evidence["alignment_miss"] += 1
            cases["alignment_miss"].append(case)
        if len(candidates) > 1:
            evidence["multiple_date_candidates"] += 1
            cases["multiple_date_candidates"].append(case)
        if normalized_reconstructed != normalized_target:
            evidence["field_reconstruction_error"] += 1
            cases["field_reconstruction_error"].append(case)
        if normalized_cleaned != normalized_target:
            evidence["field_reconstruction_error_after_cleanup"] += 1
            cases["field_reconstruction_error_after_cleanup"].append(case)
        if len(sample.tokens) >= 510:
            evidence["truncation"] += 1
            cases["truncation"].append(case)
    return {
        "sample_count": len(samples),
        "date_metric": asdict(next(metric for metric in FIRST_GPU_FIELD_METRICS if metric.field == "date")),
        "ground_truth_format_distribution": dict(formats),
        "prediction_format_distribution": "unavailable_without_cloud_prediction_details",
        "observable_evidence_counts": {
            category: evidence.get(category, 0)
            for category in [
                "ocr_missing",
                "alignment_miss",
                "multiple_date_candidates",
                "field_reconstruction_error",
                "field_reconstruction_error_after_cleanup",
                "truncation",
            ]
        },
        "unresolved_model_side_categories": [
            "model_classification_miss",
            "normalization_error",
            "unknown",
        ],
        "representative_cases": {
            category: values[:5] for category, values in cases.items()
        },
    }


def date_analysis_to_markdown(report: dict[str, object]) -> str:
    """生成不猜测模型预测的日期专项报告。"""

    metric = report["date_metric"]
    lines = [
        "# LayoutLMv3 Date Error Analysis",
        "",
        "- evaluation_split: local_validation_split_seed_42",
        "- official_test: false",
        f"- sample_count: {report['sample_count']}",
        f"- true_positive: {metric['true_positive']}",
        f"- false_positive: {metric['false_positive']}",
        f"- false_negative: {metric['false_negative']}",
        f"- precision: {metric['precision']:.4f}",
        f"- recall: {metric['recall']:.4f}",
        f"- f1: {metric['f1']:.4f}",
        "",
        "## Evidence Boundary",
        "",
        "云端逐样本 LayoutLMv3 预测和原错误报告尚未回传。本报告不猜测错误样本，"
        "只统计本地 validation 可重算的 OCR、BIO alignment、候选数、截断和金标重建证据。",
        "预测格式、model classification miss、normalization error 和 unknown "
        "需取得云端逐样本预测后补齐。",
        "",
        "## Ground Truth Date Formats",
        "",
    ]
    for name, count in report["ground_truth_format_distribution"].items():
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Observable Evidence Counts", ""])
    for name, count in report["observable_evidence_counts"].items():
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Model-side Categories Awaiting Predictions", ""])
    for name in report["unresolved_model_side_categories"]:
        lines.append(f"- {name}: unavailable_without_cloud_prediction_details")
    lines.extend(
        [
            "",
            "## Prediction Format Distribution",
            "",
            "- unavailable_without_cloud_prediction_details",
            "",
            "## Representative Cases",
            "",
        ]
    )
    for category, cases in report["representative_cases"].items():
        lines.append(f"### {category}")
        if not cases:
            lines.append("- none")
        for case in cases:
            lines.append(
                f"- `{case['sample_id']}` gt=`{case['ground_truth']}` "
                f"candidates={case['date_candidates']} reconstructed=`{case['reconstructed']}` "
                f"cleaned=`{case['cleaned_reconstructed']}` "
                f"tokens={case['token_count']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def hybrid_metrics() -> list[dict[str, object]]:
    """组合 LayoutLMv3 三字段与 Regex date，计算离线 hybrid macro。"""

    layout = {metric.field: metric for metric in FIRST_GPU_FIELD_METRICS}
    values = {
        "company": layout["company"].f1,
        "address": layout["address"].f1,
        "date": BASELINE_F1["date"],
        "total": layout["total"].f1,
    }
    rows = []
    for field, hybrid_f1 in values.items():
        rows.append(
            {
                "field": field,
                "baseline_f1": BASELINE_F1[field],
                "layoutlmv3_f1": layout[field].f1,
                "hybrid_f1": hybrid_f1,
            }
        )
    rows.append(
        {
            "field": "macro",
            "baseline_f1": BASELINE_F1["macro"],
            "layoutlmv3_f1": sum(metric.f1 for metric in FIRST_GPU_FIELD_METRICS) / 4,
            "hybrid_f1": sum(values.values()) / 4,
        }
    )
    return rows


def hybrid_report_to_markdown(rows: Iterable[dict[str, object]]) -> str:
    """生成 hybrid 与 baseline、纯 LayoutLMv3 的对比表。"""

    lines = [
        "# Hybrid Extraction Validation Report",
        "",
        "- evaluation_split: local_validation_split_seed_42",
        "- official_test: false",
        "- strategy: company/address/total=LayoutLMv3, date=OCR+Regex baseline",
        "",
        "| field | regex_baseline_f1 | layoutlmv3_f1 | hybrid_f1 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['field']} | {row['baseline_f1']:.4f} | "
            f"{row['layoutlmv3_f1']:.4f} | {row['hybrid_f1']:.4f} |"
        )
    return "\n".join(lines) + "\n"
