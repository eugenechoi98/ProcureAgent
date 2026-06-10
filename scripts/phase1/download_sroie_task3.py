"""下载 Voxel51/scanned_receipts Task 3 数据。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.hf_sroie_task3 import download_task3_repository


def main() -> None:
    """下载并输出真实字段结构。"""

    parser = argparse.ArgumentParser(description="Download labeled SROIE Task 3 dataset.")
    parser.add_argument("--dataset", default="Voxel51/scanned_receipts")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--local-image-source",
        action="append",
        default=[],
        help="Optional local image directory used before downloading duplicate source images.",
    )
    args = parser.parse_args()

    try:
        summary = download_task3_repository(
            args.dataset,
            args.output,
            local_image_sources=args.local_image_source,
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Task 3 download failed: {exc}") from exc
    print(f"sample_count={summary.sample_count}")
    print(f"field_names={summary.field_names}")
    print(f"missing_fields={summary.missing_fields}")
    print(f"duplicate_sample_ids={len(summary.duplicate_ids)}")
    print(f"cache_path={summary.cache_path}")


if __name__ == "__main__":
    main()
