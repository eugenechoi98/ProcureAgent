"""SROIE baseline 错误分析工具。"""

import json
from pathlib import Path

from procureguard.extraction.metrics import normalize_field_value
from procureguard.extraction.schemas import ErrorCase, SROIE_FIELDS

ERROR_TYPES = {
    "ocr_error",
    "regex_rule_miss",
    "layout_change",
    "low_quality",
    "missing_field",
    "normalization_issue",
    "unknown",
}


def classify_error(field: str, predicted: str, expected: str, notes_hint: str | None = None) -> tuple[str, str]:
    """用确定性规则给错误打粗分类，不调用 LLM。"""

    if not expected:
        return "missing_field", "Ground truth does not contain this field."
    if not predicted:
        return "regex_rule_miss", "Regex baseline did not produce a value."
    if normalize_field_value(predicted, field) == normalize_field_value(expected, field):
        return "normalization_issue", "Raw values differ but normalized values match."
    if notes_hint in ERROR_TYPES:
        return notes_hint, f"Fixture/manual hint marked this as {notes_hint}."
    if field in {"company", "address"}:
        return "layout_change", "Heuristic line selection likely picked the wrong region."
    return "unknown", "No deterministic category matched."


def collect_error_cases(
    sample_ids: list[str],
    predictions: list[dict[str, object]],
    references: list[dict[str, object]],
    field_names: list[str] | None = None,
    notes_hints: dict[str, dict[str, str]] | None = None,
) -> list[ErrorCase]:
    """收集字段级错误明细。"""

    fields = field_names or SROIE_FIELDS
    if not (len(sample_ids) == len(predictions) == len(references)):
        raise ValueError("Sample ids, predictions and references must have the same length.")

    errors: list[ErrorCase] = []
    for sample_id, prediction, reference in zip(sample_ids, predictions, references, strict=True):
        for field_name in fields:
            predicted_raw = prediction.get(field_name)
            expected_raw = reference.get(field_name)
            predicted = normalize_field_value(predicted_raw, field_name)
            expected = normalize_field_value(expected_raw, field_name)
            if predicted == expected:
                continue
            hint = (notes_hints or {}).get(sample_id, {}).get(field_name)
            error_type, notes = classify_error(field_name, predicted, expected, hint)
            errors.append(
                ErrorCase(
                    sample_id=sample_id,
                    field=field_name,
                    predicted=predicted or None,
                    ground_truth=expected or None,
                    error_type=error_type,
                    notes=notes,
                )
            )
    return errors


def errors_to_json(errors: list[ErrorCase]) -> list[dict[str, object]]:
    """错误案例转 JSON 友好结构。"""

    return [error.__dict__ for error in errors]


def errors_to_markdown(errors: list[ErrorCase]) -> str:
    """错误案例转 Markdown。"""

    lines = [
        "# Phase 1A Baseline Error Analysis",
        "",
        "| sample_id | field | predicted | ground_truth | error_type | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for error in errors:
        lines.append(
            f"| {error.sample_id} | {error.field} | {error.predicted or ''} | "
            f"{error.ground_truth or ''} | {error.error_type} | {error.notes} |"
        )
    return "\n".join(lines) + "\n"


def write_error_outputs(errors: list[ErrorCase], output: str | Path) -> None:
    """按扩展名写 JSON 或 Markdown 错误分析。"""

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(errors_to_json(errors), indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(errors_to_markdown(errors), encoding="utf-8")
