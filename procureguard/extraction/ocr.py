"""PaddleOCR 适配和 OCR token 标准化工具。"""

from pathlib import Path
from typing import Any, Iterable, Sequence

from procureguard.extraction.schemas import OCRToken


def _clip(value: float, lower: int, upper: int) -> int:
    """把坐标裁剪到图片边界内。"""

    return int(max(lower, min(upper, value)))


def normalize_bbox(
    points: Sequence[Sequence[float]] | Sequence[float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """把原始 bbox 归一化到 LayoutLMv3 的 0-1000 坐标空间。"""

    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be positive.")
    if len(points) == 4 and all(isinstance(value, (int, float)) for value in points):
        x0, y0, x1, y1 = [float(value) for value in points]  # type: ignore[arg-type]
    else:
        nested = points  # type: ignore[assignment]
        if not nested:
            raise ValueError("BBox points cannot be empty.")
        xs = [float(point[0]) for point in nested]  # type: ignore[index]
        ys = [float(point[1]) for point in nested]  # type: ignore[index]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

    x0 = _clip(x0, 0, width)
    y0 = _clip(y0, 0, height)
    x1 = _clip(x1, 0, width)
    y1 = _clip(y1, 0, height)
    normalized = (
        int(x0 / width * 1000),
        int(y0 / height * 1000),
        int(x1 / width * 1000),
        int(y1 / height * 1000),
    )
    return tuple(_clip(value, 0, 1000) for value in normalized)


def build_token(text: str, bbox: Sequence[int], confidence: float | None = None) -> OCRToken | None:
    """过滤空文本并构造统一 OCR token。"""

    if not text or not text.strip():
        return None
    score = 1.0 if confidence is None else float(confidence)
    return OCRToken(text=text, bbox=tuple(int(value) for value in bbox), confidence=score)


def filter_empty_tokens(tokens: Iterable[OCRToken | None]) -> list[OCRToken]:
    """过滤空 token，并保持原始 OCR 顺序。"""

    return [token for token in tokens if token is not None]


class PaddleOCRAdapter:
    """真实 PaddleOCR 适配器，只有调用时才检查可选依赖。"""

    def __init__(self, lang: str = "en", use_angle_cls: bool = True):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise ImportError(
                "PaddleOCR is not installed. Install Phase 1 dependencies before running OCR: "
                "pip install -e .[phase1]"
            ) from exc

        try:
            self.ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
                device="cpu",
            )
            self.api_version = 3
        except (TypeError, ValueError):
            self.ocr = PaddleOCR(use_angle_cls=use_angle_cls, lang=lang)
            self.api_version = 2

    def extract_tokens(self, image_path: str | Path) -> list[OCRToken]:
        """读取英文票据图片并输出统一 OCR token。"""

        from PIL import Image

        path = Path(image_path)
        with Image.open(path) as image:
            width, height = image.size
        if self.api_version == 3:
            result: list[Any] = self.ocr.predict(str(path))
            return paddleocr_v3_result_to_tokens(result, width=width, height=height)
        result = self.ocr.ocr(str(path))
        return paddleocr_result_to_tokens(result, width=width, height=height)


def paddleocr_result_to_tokens(result: list[Any], width: int, height: int) -> list[OCRToken]:
    """把 PaddleOCR 原始结果转换为统一 token。"""

    tokens: list[OCRToken | None] = []
    for page in result or []:
        for line in page or []:
            if len(line) < 2:
                continue
            raw_bbox = line[0]
            text = str(line[1][0]) if line[1] else ""
            confidence = float(line[1][1]) if len(line[1]) > 1 else 1.0
            bbox = normalize_bbox(raw_bbox, width=width, height=height)
            tokens.append(build_token(text, bbox, confidence))
    return filter_empty_tokens(tokens)


def paddleocr_v3_result_to_tokens(result: list[Any], width: int, height: int) -> list[OCRToken]:
    """把 PaddleOCR 3.x 结果转换为统一 token。"""

    tokens: list[OCRToken | None] = []
    for page in result or []:
        texts = list(page.get("rec_texts", []))
        scores = list(page.get("rec_scores", []))
        polygons = list(page.get("rec_polys", []))
        for index, text in enumerate(texts):
            if index >= len(polygons):
                continue
            confidence = float(scores[index]) if index < len(scores) else 1.0
            polygon = polygons[index]
            points = polygon.tolist() if hasattr(polygon, "tolist") else polygon
            bbox = normalize_bbox(points, width=width, height=height)
            tokens.append(build_token(str(text), bbox, confidence))
    return filter_empty_tokens(tokens)


PaddleOcrReader = PaddleOCRAdapter
