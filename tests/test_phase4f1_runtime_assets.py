"""Phase 4F.1 LayoutLMv3 runtime bundle 测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from procureguard.extraction.alignment import ID2LABEL
from scripts.phase4.prepare_layoutlmv3_runtime_assets import prepare_runtime_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_source(path: Path, *, labels: dict[int, str] | None = None) -> Path:
    """创建最小本地 checkpoint fixture，不包含真实模型。"""

    path.mkdir(parents=True)
    (path / "model.safetensors").write_bytes(b"fine-tuned-test-fixture")
    mapping = labels or ID2LABEL
    (path / "config.json").write_text(
        json.dumps({"id2label": {str(key): value for key, value in mapping.items()}}),
        encoding="utf-8",
    )
    for name in ("preprocessor_config.json", "tokenizer_config.json", "tokenizer.json"):
        (path / name).write_text("{}", encoding="utf-8")
    return path


def test_prepare_manifest_is_parseable_and_records_sha256(tmp_path: Path) -> None:
    source = make_source(tmp_path / "source")
    output = PROJECT_ROOT / "artifacts" / "test_phase4f1" / tmp_path.name

    manifest = prepare_runtime_bundle(source, output)
    saved = json.loads((output / "runtime_manifest.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "ready"
    assert saved["fine_tuned_checkpoint"] is True
    assert saved["processor_restored"] is True
    assert saved["label_map_rebuilt"] is True
    assert all(len(item["sha256"]) == 64 for item in saved["files"])
    assert (output / "label_map.json").is_file()


def test_prepare_fails_clearly_when_checkpoint_missing(tmp_path: Path) -> None:
    output = PROJECT_ROOT / "artifacts" / "test_phase4f1" / tmp_path.name

    manifest = prepare_runtime_bundle(tmp_path / "missing", output)

    assert manifest["status"] == "blocked_missing_checkpoint"
    assert manifest["fine_tuned_checkpoint"] is False
    assert json.loads((output / "runtime_manifest.json").read_text(encoding="utf-8"))["status"] == "blocked_missing_checkpoint"


def test_prepare_fails_clearly_when_processor_missing(tmp_path: Path) -> None:
    source = make_source(tmp_path / "source")
    for name in ("preprocessor_config.json", "tokenizer_config.json", "tokenizer.json"):
        (source / name).unlink()
    output = PROJECT_ROOT / "artifacts" / "test_phase4f1" / tmp_path.name

    manifest = prepare_runtime_bundle(source, output)

    assert manifest["status"] == "blocked_missing_processor"
    assert manifest["fine_tuned_checkpoint"] is True


def test_prepare_rejects_checkpoint_label_order_mismatch(tmp_path: Path) -> None:
    wrong = dict(ID2LABEL)
    wrong[1], wrong[2] = wrong[2], wrong[1]
    source = make_source(tmp_path / "source", labels=wrong)
    output = PROJECT_ROOT / "artifacts" / "test_phase4f1" / tmp_path.name

    manifest = prepare_runtime_bundle(source, output)

    assert manifest["status"] == "blocked_label_order_mismatch"
    assert manifest["label_map_rebuilt"] is False


def test_prepare_refuses_git_tracked_destination(tmp_path: Path) -> None:
    source = make_source(tmp_path / "source")

    with pytest.raises(ValueError, match="artifacts"):
        prepare_runtime_bundle(source, tmp_path / "bundle")


def test_report_does_not_claim_fake_fixture_as_live_success() -> None:
    report = json.loads(
        Path("reports/phase4/phase4f1_layoutlmv3_runtime_asset_bundle.json").read_text(
            encoding="utf-8"
        )
    ) if Path("reports/phase4/phase4f1_layoutlmv3_runtime_asset_bundle.json").exists() else None

    if report:
        assert report["fake_fixture_is_live_success_evidence"] is False
        assert report["phase2_invoked"] is False
        assert report["risk_level_generated"] is False
        assert report["recommended_action_generated"] is False
