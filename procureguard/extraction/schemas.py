"""Phase 1 数据样本、OCR token 和 baseline 输出结构。"""

from dataclasses import dataclass, field
from pathlib import Path


SROIE_FIELDS = ["company", "address", "date", "total"]


@dataclass(frozen=True)
class OCRToken:
    """统一 OCR token，bbox 固定为 LayoutLMv3 风格的 x0,y0,x1,y1。"""

    text: str
    bbox: tuple[int, int, int, int]
    confidence: float = 1.0

    def __post_init__(self) -> None:
        cleaned = self.text.strip()
        if not cleaned:
            raise ValueError("OCRToken text cannot be empty.")
        if len(self.bbox) != 4:
            raise ValueError("OCRToken bbox must contain four integers.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("OCRToken confidence must be between 0.0 and 1.0.")
        object.__setattr__(self, "text", cleaned)
        object.__setattr__(self, "bbox", tuple(int(value) for value in self.bbox))


@dataclass(frozen=True)
class BaselineField:
    """单个 baseline 字段结果。"""

    value: str | None = None
    confidence: float = 0.0
    matched_text: str | None = None
    rule_name: str | None = None


@dataclass(frozen=True)
class BaselineExtraction:
    """SROIE OCR + Regex baseline 输出，不修改后端共享 schema。"""

    baseline_name: str
    fields: dict[str, BaselineField]

    def values(self) -> dict[str, str | None]:
        """只取字段值，用于评测。"""

        return {name: field.value for name, field in self.fields.items()}

    def to_procureguard_fields(self) -> dict[str, object]:
        """映射到后续可替换 ExtractedFields 的字段名。"""

        total_value = self.fields["total"].value
        return {
            "vendor_name": self.fields["company"].value,
            "invoice_date": self.fields["date"].value,
            "total_amount": float(total_value) if total_value else None,
        }


@dataclass(frozen=True)
class SroieSample:
    """SROIE processed JSONL 样本。"""

    sample_id: str
    image_path: str
    tokens: list[OCRToken]
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedSample:
    """LayoutLMv3 训练前的统一样本。"""

    sample_id: str
    image_path: Path
    words: list[str] = field(default_factory=list)
    bboxes: list[tuple[int, int, int, int]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ErrorCase:
    """字段级错误分析案例。"""

    sample_id: str
    field: str
    predicted: str | None
    ground_truth: str | None
    error_type: str
    notes: str


OcrWord = OCRToken
