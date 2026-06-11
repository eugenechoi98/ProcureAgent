"""GPU Notebook bootstrap 的 CPU 单元测试。"""

from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys

import pytest

from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.gpu_notebook import (
    check_requirements,
    count_non_o_labels,
    evaluate_training_guard,
    install_missing_requirements,
    kernel_python_info,
    model_directory_exists,
    normalize_copy_suffix,
    read_requirement_names,
    repair_processed_jsonl_paths,
    require_successful_repairs,
    source_image_name,
)


def write_sample_jsonl(path: Path, image_path: str, sample_id: str = "sample-1") -> str:
    """写入带实体标签的最小 processed JSONL。"""

    row = {
        "sample_id": sample_id,
        "image_path": image_path,
        "tokens": [
            {
                "text": "ACME",
                "bbox": [0, 0, 100, 100],
                "confidence": 1.0,
            }
        ],
        "labels": {
            "company": "ACME",
            "address": "",
            "date": "",
            "total": "",
        },
    }
    content = json.dumps(row, ensure_ascii=False) + "\n"
    path.write_text(content, encoding="utf-8")
    return content


def test_kernel_python_path_uses_current_interpreter():
    info = kernel_python_info()

    assert Path(info["python_executable"]).resolve() == Path(sys.executable).resolve()
    assert info["python_version"]


def test_requirements_file_and_missing_dependency_check():
    names = read_requirement_names(Path("requirements/phase1-gpu.txt"))

    def fake_version(name: str) -> str:
        if name == "seqeval":
            raise metadata.PackageNotFoundError(name)
        return "1.0"

    result = check_requirements(names, version_getter=fake_version)

    assert "seqeval" in result.missing
    assert "scikit-learn" in result.installed


def test_missing_seqeval_install_failure_is_explicit(tmp_path: Path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("seqeval>=1.2.2,<2.0\n", encoding="utf-8")

    def failed_runner(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    with pytest.raises(RuntimeError, match="seqeval.*wheelhouse"):
        install_missing_requirements(
            ["seqeval"],
            requirements,
            python_executable=sys.executable,
            runner=failed_runner,
        )


def test_local_model_directory_check(tmp_path: Path):
    model_dir = tmp_path / "layoutlmv3-base"

    assert not model_directory_exists(model_dir)
    model_dir.mkdir()
    assert not model_directory_exists(model_dir)
    (model_dir / "pytorch_model.bin").write_bytes(b"legacy")
    assert not model_directory_exists(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"safe")
    assert model_directory_exists(model_dir)


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        (r"data\phase1\sroie_task3\data\receipt.jpg", "receipt.jpg"),
        ("/mnt/workspace/SROIE/imgs/receipt.jpg", "receipt.jpg"),
    ],
)
def test_windows_and_linux_image_path_name(raw_path: str, expected: str):
    assert source_image_name(raw_path) == expected


@pytest.mark.parametrize(
    "filename",
    ["receipt (1).jpg", "receipt (2).jpg", "receipt (3).jpg"],
)
def test_copy_suffix_normalization(filename: str):
    assert normalize_copy_suffix(filename) == "receipt.jpg"


def test_ambiguous_copy_suffix_is_rejected_without_rewrite(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "receipt (1).jpg").write_bytes(b"one")
    (images / "receipt (2).jpg").write_bytes(b"two")
    jsonl = tmp_path / "train.jsonl"
    original = write_sample_jsonl(jsonl, r"C:\old\receipt.jpg")

    result = repair_processed_jsonl_paths(jsonl, images)

    assert result.ambiguous == {
        "sample-1": [
            str(images / "receipt (1).jpg"),
            str(images / "receipt (2).jpg"),
        ]
    }
    assert result.backup_path is None
    assert jsonl.read_text(encoding="utf-8") == original
    with pytest.raises(RuntimeError, match="ambiguous"):
        require_successful_repairs([result])


def test_unresolved_image_is_rejected_without_rewrite(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    jsonl = tmp_path / "validation.jsonl"
    original = write_sample_jsonl(jsonl, "/old/missing.jpg")

    result = repair_processed_jsonl_paths(jsonl, images)

    assert result.unresolved == ["sample-1"]
    assert result.backup_path is None
    assert jsonl.read_text(encoding="utf-8") == original
    with pytest.raises(RuntimeError, match="unresolved"):
        require_successful_repairs([result])


def test_jsonl_backup_path_repair_sroie_loader_and_non_o_labels(tmp_path: Path):
    images = tmp_path / "images"
    images.mkdir()
    image = images / "receipt (1).jpg"
    image.write_bytes(b"image")
    jsonl = tmp_path / "train.jsonl"
    original = write_sample_jsonl(jsonl, r"C:\old\receipt.jpg")

    result = repair_processed_jsonl_paths(jsonl, images)
    samples = read_processed_jsonl(jsonl)

    assert result.changed == 1
    assert result.backup_path == jsonl.with_suffix(".jsonl.bak")
    assert result.backup_path.read_text(encoding="utf-8") == original
    assert samples[0].image_path == str(image.resolve())
    assert samples[0].__class__.__name__ == "SroieSample"
    assert count_non_o_labels(samples) > 0


def test_baseline_report_and_other_guard_conditions():
    common = {
        "cuda_available": True,
        "require_cuda": True,
        "project_import_ok": True,
        "model_dir_exists": True,
        "train_samples": 570,
        "validation_samples": 142,
        "missing_images": 0,
        "labels_non_o_count": 7,
        "seqeval_import_ok": True,
    }

    assert evaluate_training_guard(**common, baseline_report_exists=True)
    assert not evaluate_training_guard(**common, baseline_report_exists=False)
