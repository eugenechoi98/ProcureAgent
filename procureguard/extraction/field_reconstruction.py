"""把 BIO token span 稳定重建为 SROIE 字段值。"""

from __future__ import annotations

import re

from procureguard.extraction.baseline import SroieRegexBaseline, normalize_date
from procureguard.extraction.schemas import OCRToken, SROIE_FIELDS


def clean_date_span(text: str) -> str:
    """从模型标记的 DATE span 中提取日期，去掉前缀、时间和其他文本。"""

    for pattern in (
        SroieRegexBaseline.numeric_date_pattern,
        SroieRegexBaseline.text_date_pattern,
    ):
        match = pattern.search(text)
        if match:
            return normalize_date(match.group(1)) or match.group(1)
    compact = re.search(r"\b(\d{8})\b", text)
    if compact:
        value = compact.group(1)
        for reordered in (
            value,
            f"{value[6:8]}/{value[4:6]}/{value[0:4]}",
            f"{value[0:2]}/{value[2:4]}/{value[4:8]}",
        ):
            normalized = normalize_date(reordered)
            if normalized:
                return normalized
    return text.strip()


def reconstruct_bio_fields(
    tokens: list[OCRToken],
    labels: list[str],
) -> dict[str, str]:
    """按 BIO 标签重建四字段，并对 date span 做确定性清洗。"""

    if len(tokens) != len(labels):
        raise ValueError("Tokens and BIO labels must have the same length.")
    fields = {field: "" for field in SROIE_FIELDS}
    active_field: str | None = None
    for token, label in zip(tokens, labels, strict=True):
        if label == "O":
            active_field = None
            continue
        prefix, field_name = label.split("-", 1)
        field_name = field_name.lower()
        if field_name not in fields:
            active_field = None
            continue
        if prefix == "B":
            fields[field_name] = token.text
            active_field = field_name
        elif prefix == "I" and active_field == field_name:
            fields[field_name] = f"{fields[field_name]} {token.text}".strip()
    if fields["date"]:
        fields["date"] = clean_date_span(fields["date"])
    return fields
