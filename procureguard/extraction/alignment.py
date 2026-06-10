"""SROIE 字段到 OCR token 的 BIO 标签对齐。"""

from dataclasses import dataclass, field
import re

from procureguard.extraction.baseline import normalize_amount, normalize_date
from procureguard.extraction.schemas import OCRToken, SROIE_FIELDS, SroieSample

BIO_LABELS = [
    "O",
    "B-COMPANY",
    "I-COMPANY",
    "B-ADDRESS",
    "I-ADDRESS",
    "B-DATE",
    "I-DATE",
    "B-TOTAL",
    "I-TOTAL",
]
LABEL2ID = {label: index for index, label in enumerate(BIO_LABELS)}
ID2LABEL = {index: label for label, index in LABEL2ID.items()}


@dataclass(frozen=True)
class UnalignedField:
    """无法对齐的字段记录。"""

    sample_id: str
    field: str
    value: str
    reason: str


@dataclass
class AlignmentSummary:
    """字段对齐汇总。"""

    sample_count: int = 0
    total_fields: int = 0
    aligned_fields: int = 0
    unaligned_fields: int = 0
    unaligned_cases: list[UnalignedField] = field(default_factory=list)


def normalize_for_alignment(value: object, field_name: str | None = None) -> str:
    """对齐前做可解释标准化，不做不可控模糊匹配。"""

    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if field_name == "total":
        return normalize_amount(text)
    if field_name == "date":
        return normalize_date(text) or re.sub(r"[^a-z0-9]", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def token_piece(token: OCRToken, field_name: str) -> str:
    """把单个 token 转成对齐片段。"""

    if field_name == "total":
        amount = normalize_amount(token.text)
        return amount.replace(".", "") if amount else ""
    if field_name == "date":
        date = normalize_date(token.text)
        if date:
            return date.replace("-", "")
    return normalize_for_alignment(token.text)


def field_target(value: str, field_name: str) -> str:
    """把字段真值转成对齐目标。"""

    normalized = normalize_for_alignment(value, field_name)
    if field_name == "total":
        return normalized.replace(".", "")
    if field_name == "date":
        return normalized.replace("-", "")
    return normalized


def align_sample_tokens(sample: SroieSample) -> tuple[list[str], list[UnalignedField]]:
    """把一个样本的 SROIE 字段对齐成 token BIO 标签。"""

    labels = ["O"] * len(sample.tokens)
    unaligned: list[UnalignedField] = []
    for field_name in SROIE_FIELDS:
        value = sample.labels.get(field_name, "")
        if not value:
            continue
        target = field_target(value, field_name)
        if not target:
            unaligned.append(UnalignedField(sample.sample_id, field_name, value, "empty normalized target"))
            continue
        span = find_token_span(sample.tokens, target, field_name, labels)
        if span is None:
            unaligned.append(UnalignedField(sample.sample_id, field_name, value, "no contiguous token span matched"))
            continue
        start, end = span
        upper = field_name.upper()
        labels[start] = f"B-{upper}"
        for index in range(start + 1, end):
            labels[index] = f"I-{upper}"
    return labels, unaligned


def find_token_span(
    tokens: list[OCRToken],
    target: str,
    field_name: str,
    current_labels: list[str],
) -> tuple[int, int] | None:
    """确定性选择第一个未占用的连续 token span。"""

    pieces = [token_piece(token, field_name) for token in tokens]
    for start in range(len(tokens)):
        if current_labels[start] != "O":
            continue
        combined = ""
        for end in range(start, len(tokens)):
            if current_labels[end] != "O":
                break
            if not pieces[end]:
                break
            combined += pieces[end]
            if combined == target:
                return start, end + 1
            if len(combined) > len(target) or not target.startswith(combined):
                break
    return None


def align_samples(samples: list[SroieSample]) -> tuple[list[list[str]], AlignmentSummary]:
    """批量对齐并返回 labels 与汇总。"""

    all_labels: list[list[str]] = []
    summary = AlignmentSummary(sample_count=len(samples))
    for sample in samples:
        labels, unaligned = align_sample_tokens(sample)
        all_labels.append(labels)
        present_fields = [field_name for field_name in SROIE_FIELDS if sample.labels.get(field_name)]
        summary.total_fields += len(present_fields)
        summary.unaligned_fields += len(unaligned)
        summary.aligned_fields += len(present_fields) - len(unaligned)
        summary.unaligned_cases.extend(unaligned)
    return all_labels, summary
