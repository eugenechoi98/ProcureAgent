"""SROIE 数据读取和 processed JSONL 转换。"""

import json
from pathlib import Path
from typing import NamedTuple

from procureguard.extraction.ocr import build_token, normalize_bbox
from procureguard.extraction.schemas import OCRToken, SROIE_FIELDS, SroieSample

PROCUREGUARD_FIELD_MAP = {
    "company": "vendor_name",
    "date": "invoice_date",
    "total": "total_amount",
}
IMAGE_SUFFIXES = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"]


class SroieDatasetCheck(NamedTuple):
    """SROIE 数据目录检查结果。"""

    exists: bool
    sample_count: int
    missing_dirs: list[str]
    key_count: int
    box_count: int
    image_count: int


def read_sroie_key_file(path: str | Path) -> dict[str, str]:
    """读取 SROIE ground truth JSON。"""

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid SROIE key JSON: {path}") from exc
    return {field: str(data.get(field, "")).strip() for field in SROIE_FIELDS}


def read_sroie_box_file(path: str | Path, image_width: int = 1000, image_height: int = 1000) -> list[OCRToken]:
    """读取 SROIE OCR 标注文本，格式为 8 个坐标加文本。"""

    tokens: list[OCRToken] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            parts = raw.split(",", 8)
            if len(parts) < 9:
                raise ValueError(f"Invalid SROIE box line {path}:{line_number}: expected 9 columns.")
            try:
                coords = [float(value) for value in parts[:8]]
            except ValueError as exc:
                raise ValueError(f"Invalid bbox coordinate {path}:{line_number}.") from exc
            points = [[coords[i], coords[i + 1]] for i in range(0, 8, 2)]
            token = build_token(parts[8], normalize_bbox(points, image_width, image_height), 1.0)
            if token:
                tokens.append(token)
    return tokens


def image_size(path: Path | None) -> tuple[int, int]:
    """读取图片尺寸；fixture 没有图片时使用 1000 坐标空间。"""

    if path is None or not path.exists():
        return 1000, 1000
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("Pillow is required to read real SROIE image sizes. Install extraction extras.") from exc
    with Image.open(path) as image:
        return image.size


def find_sroie_file(root: Path, folder_names: list[str], stem: str, suffixes: list[str]) -> Path | None:
    """在常见 SROIE 子目录里查找同名文件。"""

    for folder_name in folder_names:
        folder = root / folder_name
        for suffix in suffixes:
            candidate = folder / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
    return None


def check_sroie_dataset(raw_dir: str | Path) -> SroieDatasetCheck:
    """检查常见 SROIE raw 目录结构和样本数量。"""

    root = Path(raw_dir)
    if not root.exists():
        return SroieDatasetCheck(False, 0, [str(root)], 0, 0, 0)

    key_dir = next((root / name for name in ["key", "entities"] if (root / name).exists()), None)
    box_dir = next((root / name for name in ["box", "ocr", "txt"] if (root / name).exists()), None)
    image_dir = next((root / name for name in ["img", "image", "images"] if (root / name).exists()), None)
    missing = [
        label
        for label, folder in [("key_or_entities", key_dir), ("box_or_ocr", box_dir), ("img_or_images", image_dir)]
        if folder is None
    ]
    key_count = len(list(key_dir.glob("*.json"))) if key_dir else len(list(root.glob("*.json")))
    box_count = len(list(box_dir.glob("*.txt"))) if box_dir else len(list(root.glob("*.txt")))
    image_count = sum(len(list(image_dir.glob(f"*{suffix}"))) for suffix in IMAGE_SUFFIXES) if image_dir else 0
    stems = set()
    if key_dir:
        stems = {path.stem for path in key_dir.glob("*.json")}
    elif key_count:
        stems = {path.stem for path in root.glob("*.json")}
    return SroieDatasetCheck(True, len(stems), missing, key_count, box_count, image_count)


def iter_sroie_samples(raw_dir: str | Path, strict: bool = True) -> tuple[list[SroieSample], list[str]] | list[SroieSample]:
    """读取一个 SROIE raw 目录，坏样本报清楚但不吞错。"""

    root = Path(raw_dir)
    if not root.exists():
        raise FileNotFoundError(f"SROIE raw directory does not exist: {root}")

    key_root = next((root / name for name in ["key", "entities"] if (root / name).exists()), None)
    key_files = sorted(key_root.glob("*.json")) if key_root else sorted(root.glob("*.json"))
    samples: list[SroieSample] = []
    errors: list[str] = []
    for key_file in key_files:
        stem = key_file.stem
        try:
            box_file = find_sroie_file(root, ["box", "ocr", "txt", "."], stem, [".txt"])
            if box_file is None:
                raise FileNotFoundError(f"Missing OCR box file for sample {stem}.")
            image_file = find_sroie_file(root, ["img", "image", "images", "."], stem, IMAGE_SUFFIXES)
            image_path = str(image_file if image_file else root / "img" / f"{stem}.jpg")
            labels = read_sroie_key_file(key_file)
            width, height = image_size(image_file)
            tokens = read_sroie_box_file(box_file, image_width=width, image_height=height)
            samples.append(SroieSample(sample_id=stem, image_path=image_path, tokens=tokens, labels=labels))
        except Exception as exc:  # noqa: BLE001 - 批处理需要带样本号聚合报错
            errors.append(f"{stem}: {exc}")
    if errors and strict:
        raise ValueError("Failed to parse some SROIE samples:\n" + "\n".join(errors))
    if strict:
        return samples
    return samples, errors


def sample_to_json(sample: SroieSample) -> dict[str, object]:
    """样本转 processed JSONL 行。"""

    return {
        "sample_id": sample.sample_id,
        "image_path": sample.image_path,
        "tokens": [
            {"text": token.text, "bbox": list(token.bbox), "confidence": token.confidence}
            for token in sample.tokens
        ],
        "labels": sample.labels,
    }


def sample_from_json(row: dict[str, object]) -> SroieSample:
    """processed JSONL 行转样本。"""

    tokens = [
        OCRToken(
            text=str(token["text"]),
            bbox=tuple(token["bbox"]),  # type: ignore[arg-type]
            confidence=float(token.get("confidence", 1.0)),  # type: ignore[union-attr]
        )
        for token in row.get("tokens", [])  # type: ignore[union-attr]
    ]
    return SroieSample(
        sample_id=str(row["sample_id"]),
        image_path=str(row["image_path"]),
        tokens=tokens,
        labels={field: str(row.get("labels", {}).get(field, "")) for field in SROIE_FIELDS},  # type: ignore[union-attr]
    )


def write_processed_jsonl(samples: list[SroieSample], output: str | Path) -> None:
    """写出 processed JSONL。"""

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample_to_json(sample), ensure_ascii=False) + "\n")


def read_processed_jsonl(path: str | Path) -> list[SroieSample]:
    """读取 processed JSONL。"""

    samples: list[SroieSample] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                samples.append(sample_from_json(json.loads(line)))
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"Invalid processed JSONL line {path}:{line_number}.") from exc
    return samples


def map_sroie_to_procureguard_fields(fields: dict[str, str]) -> dict[str, str]:
    """把 SROIE 字段映射到当前冻结的 ExtractedFields 名称。"""

    mapped: dict[str, str] = {}
    for source_name, target_name in PROCUREGUARD_FIELD_MAP.items():
        if fields.get(source_name):
            mapped[target_name] = fields[source_name]
    return mapped
