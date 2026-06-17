"""Phase 4F.2：恢复 LayoutLMv3 artifact，失败时生成重建计划。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase4.prepare_layoutlmv3_runtime_assets import (
    DEFAULT_OUTPUT,
    prepare_runtime_bundle,
)


DEFAULT_RECOVERY_ROOT = PROJECT_ROOT / "artifacts" / "phase1_recovery"
DEFAULT_REBUILD_PLAN = PROJECT_ROOT / "docs" / "phase4f2_layoutlmv3_rebuild_plan.md"
DEFAULT_SEARCH_PATHS = [
    PROJECT_ROOT / "layoutlmv3_best.zip",
    PROJECT_ROOT / "checkpoints" / "phase1" / "layoutlmv3_best.zip",
    PROJECT_ROOT / "artifacts" / "phase1" / "layoutlmv3_best.zip",
    Path(r"D:\ProcureAgent_LocalArtifacts\Phase1\layoutlmv3_best.zip"),
    Path.home() / "Downloads" / "layoutlmv3_best.zip",
    Path.home() / "Desktop" / "layoutlmv3_best.zip",
    Path.home() / "Documents" / "layoutlmv3_best.zip",
]


def recover_or_rebuild(
    *,
    artifact_zip: str | Path | None = None,
    output: str | Path = DEFAULT_OUTPUT,
    recovery_root: str | Path = DEFAULT_RECOVERY_ROOT,
    rebuild_plan: str | Path = DEFAULT_REBUILD_PLAN,
    allow_training: bool = False,
) -> dict:
    """查找 zip、恢复 runtime bundle；找不到时只生成重训计划。"""

    if allow_training:
        raise RuntimeError(
            "Training is not allowed from Phase 4F.2 recovery orchestration. "
            "Run scripts/phase1/retrain_layoutlmv3.py only after explicit user approval."
        )
    recovery = Path(recovery_root).expanduser().resolve()
    recovery.mkdir(parents=True, exist_ok=True)
    candidates = [Path(artifact_zip).expanduser().resolve()] if artifact_zip else [
        path.expanduser().resolve() for path in DEFAULT_SEARCH_PATHS
    ]
    found_zip = next((path for path in candidates if path.is_file()), None)
    result = {
        "phase": "4F.2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked_missing_artifact",
        "searched_paths": [str(path) for path in candidates],
        "artifact_zip_found": found_zip is not None,
        "artifact_zip": str(found_zip) if found_zip else None,
        "runtime_bundle": str(Path(output).expanduser().resolve()),
        "prepare_manifest": None,
        "rebuild_plan": None,
        "auto_training_started": False,
        "phase2_invoked": False,
        "risk_action_generated": False,
        "fake_checkpoint_created": False,
        "errors": [],
    }
    if found_zip is None:
        plan_path = write_rebuild_plan(rebuild_plan)
        result["status"] = "rebuild_required"
        result["rebuild_plan"] = str(plan_path)
        return result

    extract_dir = recovery / "layoutlmv3_best_extracted"
    _clear_directory(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(found_zip) as archive:
            archive.extractall(extract_dir)
    except zipfile.BadZipFile as exc:
        result["status"] = "blocked_invalid_artifact_zip"
        result["errors"].append(f"invalid zip: {exc}")
        result["rebuild_plan"] = str(write_rebuild_plan(rebuild_plan))
        return result

    checkpoint_dir = _find_checkpoint_dir(extract_dir)
    if checkpoint_dir is None:
        result["status"] = "partial_recovery"
        result["errors"].append("zip extracted but no directory containing model.safetensors was found")
        result["rebuild_plan"] = str(write_rebuild_plan(rebuild_plan))
        return result

    manifest = prepare_runtime_bundle(checkpoint_dir, output)
    result["prepare_manifest"] = manifest
    if manifest["status"] == "ready":
        result["status"] = "success"
    else:
        result["status"] = "partial_recovery"
        result["errors"].extend(manifest.get("errors", []))
        result["rebuild_plan"] = str(write_rebuild_plan(rebuild_plan))
    return result


def write_rebuild_plan(path: str | Path = DEFAULT_REBUILD_PLAN) -> Path:
    """生成不执行训练的 LayoutLMv3 重建计划。"""

    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            [
                "# Phase 4F.2 LayoutLMv3 Rebuild Plan",
                "",
                "## Trigger",
                "",
                "Use this plan only if `layoutlmv3_best.zip` and equivalent Phase 1 checkpoint artifacts cannot be recovered.",
                "The recovery orchestrator must not start training automatically.",
                "",
                "## Dataset",
                "",
                "- Source: Phase 1 SROIE / Voxel51 scanned_receipts Task 3 processed data.",
                "- Split: `local_validation_split_seed_42` with 570 train and 142 validation samples.",
                "- Images: SROIE receipt images resolved by the existing Phase 1 path resolver.",
                "- No real enterprise invoices are used.",
                "",
                "## Label Schema",
                "",
                "Use the existing nine BIO labels from `procureguard.extraction.alignment`:",
                "",
                "```text",
                "O",
                "B-COMPANY / I-COMPANY",
                "B-ADDRESS / I-ADDRESS",
                "B-DATE / I-DATE",
                "B-TOTAL / I-TOTAL",
                "```",
                "",
                "Do not change label order or field names. The new run must emit `label_map.json` and checkpoint `config.json` with identical id2label order.",
                "",
                "## Training Config",
                "",
                "- Base model: `microsoft/layoutlmv3-base`, loaded locally with `use_safetensors=True`.",
                "- Epochs: 5.",
                "- Batch size: 2, reduce to 1 on CUDA OOM.",
                "- Gradient accumulation steps: 4.",
                "- Learning rate: 1e-5.",
                "- Weight decay: 0.01.",
                "- Max grad norm: 1.0.",
                "- Seed: 42.",
                "- Save target: `checkpoints/phase1/layoutlmv3_best/`.",
                "- Runtime artifact name: `retrained_layoutlmv3_v2`.",
                "",
                "## Expected Compute",
                "",
                "- Preferred: NVIDIA A10-class GPU or equivalent.",
                "- Previous observed run: about 2 minutes per epoch on A10, roughly 10-15 minutes total plus validation/export overhead.",
                "- CPU training is not recommended for this fallback.",
                "",
                "## Reproducibility Steps",
                "",
                "1. Confirm user explicitly says `允许重训`.",
                "2. Verify Phase 1 processed JSONL and images are present.",
                "3. Run the approved `scripts/phase1/retrain_layoutlmv3.py` only after approval.",
                "4. Save model and processor with `save_pretrained`.",
                "5. Generate `label_map.json` from the verified BIO schema.",
                "6. Run `scripts/phase4/prepare_layoutlmv3_runtime_assets.py`.",
                "7. Run the Phase 4F asset checker and live extraction spike.",
                "8. Record metrics separately as retrained v2; do not overwrite prior Phase 1 evidence claims.",
                "",
                "## Risks",
                "",
                "- Re-run metrics may differ from the original checkpoint.",
                "- Dataset path or OCR annotation drift can change results.",
                "- Label order mismatch would invalidate token classification outputs.",
                "- Model weights, checkpoints and caches must remain outside Git.",
                "- Rebuilt v2 must not be described as the original Phase 1 checkpoint.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def _find_checkpoint_dir(root: Path) -> Path | None:
    """在解压目录中寻找包含 safetensors/config 的 checkpoint。"""

    for candidate in [root, *[path for path in root.rglob("*") if path.is_dir()]]:
        if (candidate / "model.safetensors").is_file():
            return candidate
    return None


def _clear_directory(path: Path) -> None:
    """只清空 artifacts 下的 recovery staging 目录。"""

    artifacts_root = (PROJECT_ROOT / "artifacts").resolve()
    resolved = path.resolve()
    if artifacts_root not in resolved.parents:
        raise ValueError(f"Refusing to clear non-artifacts path: {resolved}")
    if not resolved.exists():
        return
    for child in resolved.iterdir():
        if child.is_dir():
            _clear_directory(child)
            child.rmdir()
        else:
            child.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--recovery-root", type=Path, default=DEFAULT_RECOVERY_ROOT)
    parser.add_argument("--rebuild-plan", type=Path, default=DEFAULT_REBUILD_PLAN)
    parser.add_argument("--allow-training", action="store_true")
    args = parser.parse_args()
    result = recover_or_rebuild(
        artifact_zip=args.artifact_zip,
        output=args.output,
        recovery_root=args.recovery_root,
        rebuild_plan=args.rebuild_plan,
        allow_training=args.allow_training,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
