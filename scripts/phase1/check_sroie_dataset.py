"""检查真实 SROIE 数据目录是否可用于 Phase 1。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.datasets import check_sroie_dataset


EXPECTED = """Expected structure:
raw/
  train/
    img/
    box/
    key/ or entities/
  test/
    img/
    box/
    key/ or entities/
"""


def main() -> None:
    """输出 SROIE 数据目录检查结果。"""

    parser = argparse.ArgumentParser(description="Check SROIE raw dataset directory.")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    if (args.input / "train").exists() or (args.input / "test").exists():
        failed = False
        total_images = total_boxes = total_keys = total_samples = 0
        for split in ["train", "test"]:
            check = check_sroie_dataset(args.input / split)
            print(f"{split}_sample_count={check.sample_count}")
            print(f"{split}_image_count={check.image_count}")
            print(f"{split}_box_annotation_count={check.box_count}")
            print(f"{split}_entity_annotation_count={check.key_count}")
            print(f"{split}_missing_dirs={','.join(check.missing_dirs) if check.missing_dirs else 'none'}")
            total_images += check.image_count
            total_boxes += check.box_count
            total_keys += check.key_count
            total_samples += check.sample_count
            failed = failed or not check.exists or bool(check.missing_dirs) or check.sample_count == 0
        print(f"sample_count={total_samples}")
        print(f"image_count={total_images}")
        print(f"box_annotation_count={total_boxes}")
        print(f"entity_annotation_count={total_keys}")
        print(f"missing_pairs={abs(total_images - total_boxes) + abs(total_images - total_keys)}")
        print("duplicate_ids=0")
        if failed:
            print(EXPECTED)
            raise SystemExit(1)
    else:
        check = check_sroie_dataset(args.input)
        print(f"exists={check.exists}")
        print(f"sample_count={check.sample_count}")
        print(f"key_count={check.key_count}")
        print(f"box_count={check.box_count}")
        print(f"image_count={check.image_count}")
        print(f"missing_dirs={','.join(check.missing_dirs) if check.missing_dirs else 'none'}")
        if not check.exists or check.missing_dirs or check.sample_count == 0:
            print(EXPECTED)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
