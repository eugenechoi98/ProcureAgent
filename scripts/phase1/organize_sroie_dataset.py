"""把 ModelScope SROIE 镜像整理到项目标准目录。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.modelscope_sroie import inspect_modelscope_mirror, organize_modelscope_mirror


def main() -> None:
    """识别镜像并复制可用图片/OCR annotation。"""

    parser = argparse.ArgumentParser(description="Organize ModelScope SROIE mirror.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    inspection = inspect_modelscope_mirror(args.input)
    summary = organize_modelscope_mirror(args.input, args.output)
    print(f"train_sample_count={summary.train.image_count}")
    print(f"test_sample_count={summary.test.image_count}")
    print(f"image_count={summary.train.image_count + summary.test.image_count}")
    print(f"box_annotation_count={summary.train.annotation_count + summary.test.annotation_count}")
    print(f"entity_annotation_count={summary.train.entity_count + summary.test.entity_count}")
    print(f"train_label_count={summary.train.label_count}")
    print(f"test_label_count={summary.test.label_count}")
    print(f"train_instance_image_count={summary.train.instance_image_count}")
    print(f"test_instance_image_count={summary.test.instance_image_count}")
    print(f"instance_missing_ids={len(summary.train.missing_instance_ids) + len(summary.test.missing_instance_ids)}")
    if summary.train.missing_instance_ids or summary.test.missing_instance_ids:
        print(
            f"instance_missing_id_sample={(summary.train.missing_instance_ids + summary.test.missing_instance_ids)[:10]}"
        )
    print(f"label_keys={inspection['train_label_keys']}")
    print(f"contains_company_address_date_total={inspection['contains_entity_fields']}")
    print(f"missing_pairs={len(summary.train.missing_images) + len(summary.train.missing_annotations) + len(summary.test.missing_images) + len(summary.test.missing_annotations)}")
    print(f"duplicate_ids={len(summary.train.duplicate_ids) + len(summary.test.duplicate_ids)}")
    print(f"copied_images={summary.copied_images}")
    print(f"copied_boxes={summary.copied_boxes}")
    print(f"copied_keys={summary.copied_keys}")
    print(f"skipped_existing={summary.skipped_existing}")
    if not inspection["contains_entity_fields"]:
        print(
            "warning=ModelScope train_label.jsonl/test_label.jsonl contain crop OCR labels only; "
            "company/address/date/total ground truth is absent."
        )


if __name__ == "__main__":
    main()
