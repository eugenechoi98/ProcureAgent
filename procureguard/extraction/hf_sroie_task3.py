"""Hugging Face Voxel51/scanned_receipts Task 3 适配。"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import random
import shutil
import time
from typing import Any

from procureguard.extraction.ocr import build_token, normalize_bbox
from procureguard.extraction.schemas import OCRToken, SROIE_FIELDS, SroieSample


@dataclass(frozen=True)
class Task3DatasetSummary:
    """Task 3 本地数据摘要。"""

    sample_count: int
    field_names: list[str]
    missing_fields: dict[str, int]
    duplicate_ids: list[str]
    cache_path: str


@dataclass(frozen=True)
class Task3Split:
    """固定 seed 的 train/validation 拆分。"""

    train: list[SroieSample] = field(default_factory=list)
    validation: list[SroieSample] = field(default_factory=list)
    seed: int = 42
    evaluation_split: str = "local_validation_split_seed_42"


def download_task3_repository(
    dataset_name: str,
    output_dir: str | Path,
    cache_dir: str | Path | None = None,
    local_image_sources: list[str | Path] | None = None,
) -> Task3DatasetSummary:
    """下载 metadata 与图片到 ignored 本地目录。"""

    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ImportError(
            "huggingface_hub is required. Install extraction dependencies."
        ) from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cache = Path(cache_dir) if cache_dir else output / ".hf_cache"
    samples_path = Path(
        hf_hub_download(
            repo_id=dataset_name,
            filename="samples.json",
            repo_type="dataset",
            cache_dir=cache,
            local_dir=output,
        )
    )
    hf_hub_download(
        repo_id=dataset_name,
        filename="metadata.json",
        repo_type="dataset",
        cache_dir=cache,
        local_dir=output,
    )
    rows = read_task3_rows(samples_path)
    data_dir = output / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    source_dirs = [Path(path) for path in local_image_sources or []]
    missing_files: list[str] = []
    for row in rows:
        relative_path = Path(str(row.get("filepath", "")))
        target = output / relative_path
        if target.exists():
            continue
        source = next(
            (directory / relative_path.name for directory in source_dirs if (directory / relative_path.name).exists()),
            None,
        )
        if source:
            shutil.copy2(source, target)
        else:
            missing_files.append(relative_path.as_posix())

    for filename in missing_files:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                hf_hub_download(
                    repo_id=dataset_name,
                    filename=filename,
                    repo_type="dataset",
                    cache_dir=cache,
                    local_dir=output,
                )
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - 网络下载需要重试
                last_error = exc
                time.sleep(2**attempt)
        if last_error:
            raise RuntimeError(f"Failed to download {filename}: {last_error}") from last_error
    return inspect_task3_metadata(samples_path, cache_path=str(cache.resolve()))


def inspect_task3_metadata(
    samples_path: str | Path,
    cache_path: str | None = None,
) -> Task3DatasetSummary:
    """检查 FiftyOne samples.json 的字段与完整性。"""

    rows = read_task3_rows(samples_path)
    ids = [task3_sample_id(row) for row in rows]
    duplicates = sorted({sample_id for sample_id in ids if ids.count(sample_id) > 1})
    missing = {
        field_name: sum(not str(row.get(field_name, "")).strip() for row in rows)
        for field_name in SROIE_FIELDS
    }
    fields = sorted({key for row in rows[:10] for key in row})
    return Task3DatasetSummary(
        sample_count=len(rows),
        field_names=fields,
        missing_fields=missing,
        duplicate_ids=duplicates,
        cache_path=cache_path or str(Path(samples_path).resolve().parent),
    )


def read_task3_rows(samples_path: str | Path) -> list[dict[str, Any]]:
    """读取 FiftyOne samples.json。"""

    try:
        payload = json.loads(Path(samples_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Task 3 samples JSON: {samples_path}") from exc
    rows = payload.get("samples")
    if not isinstance(rows, list):
        raise ValueError("Task 3 samples.json must contain a samples list.")
    return rows


def task3_sample_id(row: dict[str, Any]) -> str:
    """生成稳定 sample id。"""

    object_id = row.get("_id", {})
    if isinstance(object_id, dict) and object_id.get("$oid"):
        return str(object_id["$oid"])
    return Path(str(row.get("filepath", ""))).stem


def convert_task3_row(row: dict[str, Any], dataset_root: str | Path) -> SroieSample:
    """把 FiftyOne sample 转成统一 SroieSample。"""

    root = Path(dataset_root)
    metadata = row.get("metadata") or {}
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions for sample {task3_sample_id(row)}.")

    detections = (row.get("text_detections") or {}).get("detections") or []
    tokens: list[OCRToken] = []
    for detection in detections:
        text = str(detection.get("label", ""))
        bounding_box = detection.get("bounding_box")
        if not isinstance(bounding_box, list) or len(bounding_box) != 4:
            continue
        x, y, box_width, box_height = [float(value) for value in bounding_box]
        pixel_bbox = [
            x * width,
            y * height,
            (x + box_width) * width,
            (y + box_height) * height,
        ]
        token = build_token(text, normalize_bbox(pixel_bbox, width, height), 1.0)
        if token:
            tokens.append(token)
    if not tokens:
        raise ValueError(f"No OCR detections for sample {task3_sample_id(row)}.")

    labels = {field_name: str(row.get(field_name, "") or "").strip() for field_name in SROIE_FIELDS}
    image_path = root / str(row.get("filepath", ""))
    return SroieSample(
        sample_id=task3_sample_id(row),
        image_path=str(image_path),
        tokens=tokens,
        labels=labels,
    )


def convert_task3_dataset(
    samples_path: str | Path,
    dataset_root: str | Path,
) -> tuple[list[SroieSample], list[str], dict[str, int]]:
    """转换完整 Task 3 数据集，坏样本保留 warning。"""

    samples: list[SroieSample] = []
    errors: list[str] = []
    missing_fields = {field_name: 0 for field_name in SROIE_FIELDS}
    for row in read_task3_rows(samples_path):
        sample_id = task3_sample_id(row)
        try:
            sample = convert_task3_row(row, dataset_root)
            for field_name, value in sample.labels.items():
                missing_fields[field_name] += int(not value)
            samples.append(sample)
        except Exception as exc:  # noqa: BLE001 - 批处理需要保留坏样本编号
            errors.append(f"{sample_id}: {exc}")
    return samples, errors, missing_fields


def split_task3_samples(
    samples: list[SroieSample],
    seed: int = 42,
    validation_ratio: float = 0.2,
) -> Task3Split:
    """固定 seed 拆分 train/validation。"""

    if not 0.0 < validation_ratio < 1.0:
        raise ValueError("validation_ratio must be between 0 and 1.")
    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    validation_count = max(1, round(len(shuffled) * validation_ratio))
    validation = shuffled[:validation_count]
    train = shuffled[validation_count:]
    return Task3Split(train=train, validation=validation, seed=seed)


def copy_task3_metadata(source: str | Path, target: str | Path) -> None:
    """复制 metadata 文件，不覆盖不同内容。"""

    source_path = Path(source)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        if source_path.read_bytes() != target_path.read_bytes():
            raise FileExistsError(f"Task 3 metadata conflict: {target_path}")
        return
    shutil.copy2(source_path, target_path)
