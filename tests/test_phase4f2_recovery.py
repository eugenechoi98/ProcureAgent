"""Phase 4F.2 artifact recovery 与 rebuild fallback 测试。"""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from procureguard.extraction.alignment import ID2LABEL
from scripts.phase4.recover_or_rebuild_layoutlmv3_assets import (
    recover_or_rebuild,
    write_rebuild_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_checkpoint(path: Path, *, include_processor: bool = True) -> Path:
    path.mkdir(parents=True)
    (path / "model.safetensors").write_bytes(b"fake-fine-tuned-fixture")
    (path / "config.json").write_text(
        json.dumps({"id2label": {str(key): value for key, value in ID2LABEL.items()}}),
        encoding="utf-8",
    )
    if include_processor:
        for name in ("preprocessor_config.json", "tokenizer_config.json", "tokenizer.json"):
            (path / name).write_text("{}", encoding="utf-8")
    return path


def make_zip(source_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for file in source_dir.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(source_dir.parent))
    return zip_path


def artifact_output(name: str) -> Path:
    return PROJECT_ROOT / "artifacts" / "test_phase4f2" / name


def test_zip_exists_recovers_runtime_bundle(tmp_path: Path) -> None:
    checkpoint = make_checkpoint(tmp_path / "layoutlmv3_best")
    artifact = make_zip(checkpoint, tmp_path / "layoutlmv3_best.zip")
    output = artifact_output(f"success-{tmp_path.name}")

    result = recover_or_rebuild(
        artifact_zip=artifact,
        output=output,
        recovery_root=artifact_output(f"recovery-{tmp_path.name}"),
        rebuild_plan=tmp_path / "plan.md",
    )

    assert result["status"] == "success"
    assert result["artifact_zip_found"] is True
    assert result["prepare_manifest"]["status"] == "ready"
    assert (output / "runtime_manifest.json").is_file()
    assert (output / "label_map.json").is_file()


def test_zip_incomplete_marks_partial_recovery(tmp_path: Path) -> None:
    checkpoint = make_checkpoint(tmp_path / "layoutlmv3_best", include_processor=False)
    artifact = make_zip(checkpoint, tmp_path / "layoutlmv3_best.zip")

    result = recover_or_rebuild(
        artifact_zip=artifact,
        output=artifact_output(f"partial-{tmp_path.name}"),
        recovery_root=artifact_output(f"partial-recovery-{tmp_path.name}"),
        rebuild_plan=tmp_path / "plan.md",
    )

    assert result["status"] == "partial_recovery"
    assert result["prepare_manifest"]["status"] == "blocked_missing_processor"
    assert Path(result["rebuild_plan"]).is_file()


def test_zip_missing_generates_rebuild_plan(tmp_path: Path) -> None:
    result = recover_or_rebuild(
        artifact_zip=tmp_path / "missing.zip",
        output=artifact_output(f"missing-{tmp_path.name}"),
        recovery_root=artifact_output(f"missing-recovery-{tmp_path.name}"),
        rebuild_plan=tmp_path / "plan.md",
    )

    assert result["status"] == "rebuild_required"
    assert result["artifact_zip_found"] is False
    assert Path(result["rebuild_plan"]).is_file()


def test_rebuild_plan_contains_required_contract(tmp_path: Path) -> None:
    plan = write_rebuild_plan(tmp_path / "plan.md")
    text = plan.read_text(encoding="utf-8")

    assert "Voxel51 scanned_receipts" in text
    assert "B-COMPANY" in text
    assert "Learning rate: 1e-5" in text
    assert "retrained_layoutlmv3_v2" in text
    assert "允许重训" in text


def test_no_auto_training_even_with_allow_training_flag(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Training is not allowed"):
        recover_or_rebuild(
            artifact_zip=tmp_path / "missing.zip",
            output=artifact_output(f"no-training-{tmp_path.name}"),
            recovery_root=artifact_output(f"no-training-recovery-{tmp_path.name}"),
            rebuild_plan=tmp_path / "plan.md",
            allow_training=True,
        )


def test_recovery_result_never_claims_phase2_or_risk_action(tmp_path: Path) -> None:
    result = recover_or_rebuild(
        artifact_zip=tmp_path / "missing.zip",
        output=artifact_output(f"boundary-{tmp_path.name}"),
        recovery_root=artifact_output(f"boundary-recovery-{tmp_path.name}"),
        rebuild_plan=tmp_path / "plan.md",
    )

    assert result["phase2_invoked"] is False
    assert result["risk_action_generated"] is False
    assert result["fake_checkpoint_created"] is False
