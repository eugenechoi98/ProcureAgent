"""把已有 Phase 1 产物整理为不进入 Git 的本地 runtime bundle。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.extraction.alignment import BIO_LABELS, ID2LABEL, LABEL2ID


DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "phase1_runtime" / "layoutlmv3_sroie_corrected"
PROCESSOR_FILES = (
    "preprocessor_config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
)


def prepare_runtime_bundle(
    checkpoint: str | Path,
    output: str | Path,
    *,
    base_processor: str | Path | None = None,
) -> dict:
    """复制可证明匹配的 checkpoint，并重建显式 BIO label map。"""

    source = Path(checkpoint).expanduser().resolve()
    destination = Path(output).expanduser().resolve()
    _require_ignored_artifact_destination(destination)
    destination.mkdir(parents=True, exist_ok=True)

    manifest = {
        "bundle_version": "phase4f1-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked_missing_checkpoint",
        "source_checkpoint": str(source),
        "base_processor_source": str(Path(base_processor).expanduser().resolve()) if base_processor else None,
        "output_directory": str(destination),
        "fine_tuned_checkpoint": False,
        "processor_restored": False,
        "label_map_rebuilt": False,
        "label_map_basis": "procureguard.extraction.alignment.BIO_LABELS",
        "download_attempted": False,
        "files": [],
        "errors": [],
    }
    weights = source / "model.safetensors"
    config = source / "config.json"
    if not weights.is_file():
        manifest["errors"].append(f"missing fine-tuned checkpoint: {weights}")
        return _write_bundle_metadata(destination, manifest)
    if not config.is_file():
        manifest["status"] = "blocked_missing_model_config"
        manifest["errors"].append(f"missing model config: {config}")
        return _write_bundle_metadata(destination, manifest)

    config_payload = json.loads(config.read_text(encoding="utf-8"))
    config_labels = _ordered_labels(config_payload.get("id2label", {}))
    if config_labels != list(BIO_LABELS):
        manifest["status"] = "blocked_label_order_mismatch"
        manifest["errors"].append(
            f"checkpoint label order {config_labels} does not match Phase 1 BIO labels {BIO_LABELS}"
        )
        return _write_bundle_metadata(destination, manifest)

    _copy(weights, destination / weights.name, source, manifest)
    _copy(config, destination / config.name, source, manifest)
    manifest["fine_tuned_checkpoint"] = True

    processor_source = source if _processor_ready(source) else (
        Path(base_processor).expanduser().resolve() if base_processor else None
    )
    if processor_source is None or not _processor_ready(processor_source):
        manifest["status"] = "blocked_missing_processor"
        manifest["errors"].append(
            "saved processor is missing; provide --base-processor pointing to the matching local LayoutLMv3 base processor"
        )
        return _write_bundle_metadata(destination, manifest)
    for name in PROCESSOR_FILES:
        candidate = processor_source / name
        if candidate.is_file():
            _copy(candidate, destination / name, processor_source, manifest)
    manifest["processor_restored"] = True

    label_map = {
        "labels": list(BIO_LABELS),
        "id2label": {str(key): value for key, value in ID2LABEL.items()},
        "label2id": LABEL2ID,
        "source": "procureguard.extraction.alignment",
        "verified_against_checkpoint_config": True,
    }
    label_path = destination / "label_map.json"
    label_path.write_text(json.dumps(label_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _record_file(label_path, "generated_from_phase1_alignment", manifest)
    manifest["label_map_rebuilt"] = True
    manifest["status"] = "ready"
    return _write_bundle_metadata(destination, manifest)


def _require_ignored_artifact_destination(destination: Path) -> None:
    artifacts_root = (PROJECT_ROOT / "artifacts").resolve()
    if artifacts_root not in destination.parents:
        raise ValueError(f"Runtime bundle must stay under ignored artifacts/: {destination}")


def _ordered_labels(mapping: dict) -> list[str]:
    return [
        str(mapping[str(index)] if str(index) in mapping else mapping[index])
        for index in range(len(mapping))
    ]


def _processor_ready(path: Path) -> bool:
    tokenizer = (path / "tokenizer.json").is_file() or (
        (path / "vocab.json").is_file() and (path / "merges.txt").is_file()
    )
    return (
        (path / "preprocessor_config.json").is_file()
        and (path / "tokenizer_config.json").is_file()
        and tokenizer
    )


def _copy(source: Path, target: Path, source_root: Path, manifest: dict) -> None:
    shutil.copy2(source, target)
    _record_file(target, str(source_root), manifest)


def _record_file(path: Path, source: str, manifest: dict) -> None:
    manifest["files"] = [item for item in manifest["files"] if item["name"] != path.name]
    manifest["files"].append(
        {
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": _sha256(path),
            "source": source,
        }
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_bundle_metadata(destination: Path, manifest: dict) -> dict:
    manifest_path = destination / "runtime_manifest.json"
    readme_path = destination / "README.md"
    readme_path.write_text(
        "# Local LayoutLMv3 Runtime Bundle\n\n"
        f"Status: `{manifest['status']}`\n\n"
        "This ignored local directory is not committed to Git. It must contain the fine-tuned Phase 1 checkpoint, matching processor and verified BIO label map before live extraction.\n",
        encoding="utf-8",
    )
    _record_file(readme_path, "generated_by_prepare_script", manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=PROJECT_ROOT / "checkpoints" / "phase1" / "layoutlmv3_best",
    )
    parser.add_argument("--base-processor", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = prepare_runtime_bundle(
        args.checkpoint,
        args.output,
        base_processor=args.base_processor,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
