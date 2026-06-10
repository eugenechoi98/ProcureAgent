"""ModelScope SROIE 镜像结构识别与标准目录整理。"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil


@dataclass(frozen=True)
class MirrorSplitSummary:
    """单个镜像 split 的配对统计。"""

    split: str
    image_count: int
    annotation_count: int
    label_count: int
    entity_count: int
    instance_image_count: int
    missing_images: list[str] = field(default_factory=list)
    missing_annotations: list[str] = field(default_factory=list)
    missing_instance_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OrganizeSummary:
    """镜像整理结果。"""

    train: MirrorSplitSummary
    test: MirrorSplitSummary
    copied_images: int
    copied_boxes: int
    copied_keys: int
    skipped_existing: int


def inspect_modelscope_mirror(root: str | Path) -> dict[str, object]:
    """识别当前 ModelScope 镜像结构和标签字段。"""

    source = Path(root)
    required = [
        source / "annotations" / "training",
        source / "annotations" / "test",
        source / "imgs" / "training",
        source / "imgs" / "test",
        source / "train_label.jsonl",
        source / "test_label.jsonl",
        source / "instances_training.json",
        source / "instances_test.json",
    ]
    missing = [str(path.relative_to(source)) for path in required if not path.exists()]
    if missing:
        raise ValueError(f"ModelScope SROIE mirror is incomplete: {', '.join(missing)}")

    train_keys, train_rows, train_duplicates = inspect_jsonl(source / "train_label.jsonl")
    test_keys, test_rows, test_duplicates = inspect_jsonl(source / "test_label.jsonl")
    train = inspect_split(
        source,
        "training",
        train_rows,
        train_duplicates,
        source / "instances_training.json",
    )
    test = inspect_split(
        source,
        "test",
        test_rows,
        test_duplicates,
        source / "instances_test.json",
    )
    entity_fields = {"company", "address", "date", "total"}
    return {
        "train": train,
        "test": test,
        "train_label_keys": sorted(train_keys),
        "test_label_keys": sorted(test_keys),
        "contains_entity_fields": entity_fields.issubset(train_keys) or entity_fields.issubset(test_keys),
    }


def inspect_jsonl(path: Path) -> tuple[set[str], int, list[str]]:
    """读取 JSONL 字段、行数和重复 filename。"""

    keys: set[str] = set()
    seen: set[str] = set()
    duplicates: list[str] = []
    rows = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row must be an object at {path}:{line_number}")
            keys.update(row)
            filename = str(row.get("filename", ""))
            if filename in seen:
                duplicates.append(filename)
            seen.add(filename)
            rows += 1
    return keys, rows, duplicates


def inspect_split(
    root: Path,
    mirror_split: str,
    label_count: int,
    label_duplicates: list[str],
    instances_path: Path,
) -> MirrorSplitSummary:
    """检查图片和 annotation 的 sample id 配对。"""

    image_ids = [path.stem for path in (root / "imgs" / mirror_split).iterdir() if path.is_file()]
    annotation_ids = [
        path.stem for path in (root / "annotations" / mirror_split).glob("*.txt")
    ]
    image_set = set(image_ids)
    annotation_set = set(annotation_ids)
    instances = json.loads(instances_path.read_text(encoding="utf-8"))
    instance_ids = {
        Path(str(image["file_name"])).stem
        for image in instances.get("images", [])
    }
    duplicate_ids = sorted(
        {sample_id for sample_id in image_ids if image_ids.count(sample_id) > 1}
        | {sample_id for sample_id in annotation_ids if annotation_ids.count(sample_id) > 1}
    )
    return MirrorSplitSummary(
        split=mirror_split,
        image_count=len(image_ids),
        annotation_count=len(annotation_ids),
        label_count=label_count,
        entity_count=0,
        instance_image_count=len(instance_ids),
        missing_images=sorted(annotation_set - image_set),
        missing_annotations=sorted(image_set - annotation_set),
        missing_instance_ids=sorted(image_set - instance_ids),
        duplicate_ids=sorted(set(duplicate_ids) | set(label_duplicates)),
    )


def organize_modelscope_mirror(input_dir: str | Path, output_dir: str | Path) -> OrganizeSummary:
    """复制 ModelScope 镜像的图片和 OCR annotation 到标准目录。"""

    source = Path(input_dir)
    output = Path(output_dir)
    inspection = inspect_modelscope_mirror(source)
    copied_images = copied_boxes = copied_keys = skipped = 0

    for mirror_split, target_split in [("training", "train"), ("test", "test")]:
        image_source = source / "imgs" / mirror_split
        box_source = source / "annotations" / mirror_split
        image_target = output / target_split / "img"
        box_target = output / target_split / "box"
        key_target = output / target_split / "key"
        image_target.mkdir(parents=True, exist_ok=True)
        box_target.mkdir(parents=True, exist_ok=True)
        key_target.mkdir(parents=True, exist_ok=True)

        for path in sorted(image_source.iterdir()):
            if path.is_file():
                copied = copy_idempotent(path, image_target / path.name)
                copied_images += int(copied)
                skipped += int(not copied)
        for path in sorted(box_source.glob("*.txt")):
            copied = copy_idempotent(path, box_target / path.name)
            copied_boxes += int(copied)
            skipped += int(not copied)

    return OrganizeSummary(
        train=inspection["train"],  # type: ignore[arg-type]
        test=inspection["test"],  # type: ignore[arg-type]
        copied_images=copied_images,
        copied_boxes=copied_boxes,
        copied_keys=copied_keys,
        skipped_existing=skipped,
    )


def copy_idempotent(source: Path, target: Path) -> bool:
    """复制文件；同内容文件跳过，冲突内容报错。"""

    if target.exists():
        if source.stat().st_size == target.stat().st_size and source.read_bytes() == target.read_bytes():
            return False
        raise FileExistsError(f"Target file conflict: {target}")
    shutil.copy2(source, target)
    return True
