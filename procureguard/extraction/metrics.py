"""SROIE 字段级 Precision、Recall 和 F1 评测。"""

from dataclasses import asdict, dataclass
import json
import re
import time
from pathlib import Path

from procureguard.extraction.baseline import normalize_amount, normalize_date
from procureguard.extraction.schemas import SROIE_FIELDS


@dataclass(frozen=True)
class FieldMetric:
    """单个字段的匹配统计。"""

    field: str
    precision: float
    recall: float
    f1: float
    support: int
    true_positive: int
    false_positive: int
    false_negative: int


def normalize_field_value(value: object, field_name: str | None = None) -> str:
    """字段值标准化：trim、lowercase、空格、金额和日期。"""

    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if not text:
        return ""
    if field_name == "total":
        return normalize_amount(text)
    if field_name == "date":
        return normalize_date(text) or text
    return text


def evaluate_field_f1(
    predictions: list[dict[str, object]],
    references: list[dict[str, object]],
    field_names: list[str] | None = None,
) -> list[FieldMetric]:
    """按 normalized exact match 统计字段级 F1。"""

    fields = field_names or SROIE_FIELDS
    if len(predictions) != len(references):
        raise ValueError("Predictions and references must have the same length.")

    metrics: list[FieldMetric] = []
    for field_name in fields:
        tp = fp = fn = support = 0
        for prediction, reference in zip(predictions, references, strict=True):
            predicted = normalize_field_value(prediction.get(field_name), field_name)
            expected = normalize_field_value(reference.get(field_name), field_name)
            if expected:
                support += 1
            if predicted and predicted == expected:
                tp += 1
            elif predicted and predicted != expected:
                fp += 1
                if expected:
                    fn += 1
            elif expected:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics.append(FieldMetric(field_name, precision, recall, f1, support, tp, fp, fn))
    return metrics


def add_macro_metric(metrics: list[FieldMetric]) -> list[FieldMetric]:
    """追加 macro 平均行。"""

    if not metrics:
        return []
    count = len(metrics)
    return [
        *metrics,
        FieldMetric(
            field="macro",
            precision=sum(metric.precision for metric in metrics) / count,
            recall=sum(metric.recall for metric in metrics) / count,
            f1=sum(metric.f1 for metric in metrics) / count,
            support=sum(metric.support for metric in metrics),
            true_positive=sum(metric.true_positive for metric in metrics),
            false_positive=sum(metric.false_positive for metric in metrics),
            false_negative=sum(metric.false_negative for metric in metrics),
        ),
    ]


def build_evaluation_report(
    *,
    baseline_name: str,
    predictions: list[dict[str, object]],
    references: list[dict[str, object]],
    sample_count: int,
    data_source: str,
    is_fixture: bool,
    started_at: float,
) -> dict[str, object]:
    """生成 JSON 报告结构。"""

    metrics = add_macro_metric(evaluate_field_f1(predictions, references, SROIE_FIELDS))
    return {
        "baseline_name": baseline_name,
        "sample_count": sample_count,
        "runtime_seconds": round(time.perf_counter() - started_at, 4),
        "data_source": data_source,
        "is_fixture": is_fixture,
        "matching": "normalized_exact_match",
        "metrics": [asdict(metric) for metric in metrics],
    }


def write_json_report(report: dict[str, object], path: str | Path) -> None:
    """写入 JSON 报告。"""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def metrics_to_markdown(report: dict[str, object]) -> str:
    """把字段评测报告转成 Markdown。"""

    lines = [
        f"# {report['baseline_name']} Field F1",
        "",
        f"- sample_count: {report['sample_count']}",
        f"- runtime_seconds: {report['runtime_seconds']}",
        f"- data_source: {report['data_source']}",
        f"- evaluation_split: {report.get('evaluation_split', 'unspecified')}",
        f"- is_fixture: {report['is_fixture']}",
        f"- matching: {report['matching']}",
        f"- error_count: {report.get('error_count', 'not_recorded')}",
        "",
        "| field | precision | recall | f1 | support |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for metric in report["metrics"]:  # type: ignore[index]
        lines.append(
            f"| {metric['field']} | {metric['precision']:.4f} | {metric['recall']:.4f} | "
            f"{metric['f1']:.4f} | {metric['support']} |"
        )
    return "\n".join(lines) + "\n"
