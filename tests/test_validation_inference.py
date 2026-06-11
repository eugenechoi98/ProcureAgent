"""Phase 1G checkpoint inference 与日期重建对比测试。"""

from pathlib import Path
import json

import pytest

from procureguard.extraction.schemas import OCRToken, SroieSample
from procureguard.extraction.phase1g_paths import (
    build_phase1g_paths,
    require_phase1g_paths,
    resolve_image_root,
    resolve_project_root,
)
from procureguard.extraction.validation_inference import (
    compare_reconstruction,
    comparison_to_markdown,
    reconstruct_bio_fields_legacy,
    resolve_sample_images,
    word_labels_from_predictions,
    write_comparison_outputs,
)


def date_sample(sample_id: str, expected: str, token_texts: list[str]) -> SroieSample:
    """构造日期重建对比样本。"""

    return SroieSample(
        sample_id=sample_id,
        image_path=f"{sample_id}.jpg",
        tokens=[
            OCRToken(text=text, bbox=(0, index * 10, 100, index * 10 + 8))
            for index, text in enumerate(token_texts)
        ],
        labels={"company": "", "address": "", "date": expected, "total": ""},
    )


def test_legacy_reconstruction_keeps_prefix_and_time():
    sample = date_sample("one", "30-04-2018", ["DATE:", "30-04-2018", "19:50:14"])

    fields = reconstruct_bio_fields_legacy(
        sample.tokens,
        ["B-DATE", "I-DATE", "I-DATE"],
    )

    assert fields["date"] == "DATE: 30-04-2018 19:50:14"


def test_word_labels_use_first_subword_prediction():
    labels = word_labels_from_predictions(
        [0, 3, 4, 0],
        [None, 0, 0, 1],
        word_count=2,
    )

    assert labels == ["B-ADDRESS", "O"]


def test_compare_reconstruction_reports_actual_recovery():
    samples = [
        date_sample("one", "30-04-2018", ["DATE:", "30-04-2018", "19:50:14"]),
        date_sample("two", "20/06/2018", ["20/06/2018"]),
    ]
    predicted_labels = [
        ["B-DATE", "I-DATE", "I-DATE"],
        ["B-DATE"],
    ]

    report = compare_reconstruction(samples, predicted_labels)

    assert report["legacy_date_metric"]["f1"] == pytest.approx(0.5)
    assert report["cleaned_date_metric"]["f1"] == pytest.approx(1.0)
    assert report["date_f1_recovery"] == pytest.approx(0.5)
    assert report["recommendation"] == "pure_layoutlmv3_date_path"
    assert report["evaluation_split"] == "local_validation_split_seed_42"
    assert len(report["cleaned_field_metrics"]) == 4


def test_resolve_sample_images_does_not_rewrite_source_path(tmp_path: Path):
    image = tmp_path / "nested" / "receipt.jpg"
    image.parent.mkdir()
    image.write_bytes(b"fixture")
    original = date_sample("one", "30-04-2018", ["DATE 30-04-2018"])
    original = SroieSample(
        sample_id=original.sample_id,
        image_path=r"data\phase1\sroie_task3\data\receipt.jpg",
        tokens=original.tokens,
        labels=original.labels,
    )

    resolved = resolve_sample_images([original], tmp_path)

    assert resolved[0].image_path == str(image.resolve())
    assert original.image_path == r"data\phase1\sroie_task3\data\receipt.jpg"


def write_project_markers(root: Path) -> None:
    """创建项目根目录识别 fixture。"""

    (root / "procureguard").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# fixture\n", encoding="utf-8")


def test_project_root_resolver_accepts_repository_cwd(tmp_path: Path):
    write_project_markers(tmp_path)

    assert resolve_project_root(tmp_path) == tmp_path.resolve()


def test_project_root_resolver_accepts_repository_parent_cwd(tmp_path: Path):
    root = tmp_path / "ProcureAgent"
    write_project_markers(root)

    assert resolve_project_root(tmp_path) == root.resolve()


def test_phase1g_path_check_reports_missing_script(tmp_path: Path):
    write_project_markers(tmp_path)
    image_root = tmp_path / "images"
    image_root.mkdir()
    paths = build_phase1g_paths(tmp_path, image_root=image_root)

    with pytest.raises(FileNotFoundError, match=r"script: .*compare_date_reconstruction\.py"):
        require_phase1g_paths(paths)


def test_explicit_image_root_has_priority(tmp_path: Path):
    explicit = tmp_path / "explicit"
    modelscope = tmp_path / "workspace" / "SROIE" / "unpacked" / "sroie" / "imgs"
    repository = tmp_path / "repo" / "data" / "phase1" / "sroie_task3" / "data"
    for path in (explicit, modelscope, repository):
        path.mkdir(parents=True)

    resolved = resolve_image_root(
        tmp_path / "repo",
        explicit=explicit,
        workspace_root=tmp_path / "workspace",
        environ={},
    )

    assert resolved == explicit.resolve()


def test_modelscope_image_root_candidate(tmp_path: Path):
    root = tmp_path / "workspace" / "ProcureAgent"
    modelscope = tmp_path / "workspace" / "SROIE" / "unpacked" / "sroie" / "imgs"
    modelscope.mkdir(parents=True)

    resolved = resolve_image_root(root, environ={})

    assert resolved == modelscope.resolve()


def test_environment_image_root_precedes_modelscope_candidate(tmp_path: Path):
    root = tmp_path / "workspace" / "ProcureAgent"
    environment_root = tmp_path / "environment-images"
    modelscope = tmp_path / "workspace" / "SROIE" / "unpacked" / "sroie" / "imgs"
    environment_root.mkdir()
    modelscope.mkdir(parents=True)

    resolved = resolve_image_root(
        root,
        environ={"PROCUREGUARD_PHASE1G_IMAGE_ROOT": str(environment_root)},
    )

    assert resolved == environment_root.resolve()


def test_repository_image_root_fallback(tmp_path: Path):
    root = tmp_path / "ProcureAgent"
    repository = root / "data" / "phase1" / "sroie_task3" / "data"
    repository.mkdir(parents=True)

    resolved = resolve_image_root(root, environ={})

    assert resolved == repository.resolve()


def test_missing_image_roots_list_all_attempts(tmp_path: Path):
    root = tmp_path / "workspace" / "ProcureAgent"
    explicit = tmp_path / "missing-explicit"

    with pytest.raises(FileNotFoundError) as error:
        resolve_image_root(
            root,
            explicit=explicit,
            environ={"SROIE_IMAGE_ROOT": str(tmp_path / "missing-env")},
        )

    message = str(error.value)
    assert str(explicit.resolve()) in message
    assert str((tmp_path / "missing-env").resolve()) in message
    assert str((root.parent / "SROIE" / "unpacked" / "sroie" / "imgs").resolve()) in message
    assert str((root / "data" / "phase1" / "sroie_task3" / "data").resolve()) in message


@pytest.mark.parametrize("suffix", [" (1)", " (2)", " (3)"])
def test_windows_jsonl_path_resolves_copy_suffix_in_memory(tmp_path: Path, suffix: str):
    image = tmp_path / f"receipt{suffix}.jpg"
    image.write_bytes(b"fixture")
    original = SroieSample(
        sample_id="one",
        image_path=r"C:\dataset\receipt.jpg",
        tokens=[],
        labels={"company": "", "address": "", "date": "", "total": ""},
    )

    resolved = resolve_sample_images([original], tmp_path)

    assert resolved[0].image_path == str(image.resolve())
    assert original.image_path == r"C:\dataset\receipt.jpg"


def test_comparison_report_and_outputs(tmp_path: Path):
    report = compare_reconstruction(
        [date_sample("one", "30-04-2018", ["DATE:", "30-04-2018"])],
        [["B-DATE", "I-DATE"]],
    )

    paths = write_comparison_outputs(report, tmp_path)
    markdown = comparison_to_markdown(report)

    assert set(paths) == {"json", "markdown", "predictions"}
    assert all(path.is_file() for path in paths.values())
    assert "date_f1_recovery" in markdown
    assert "integrated_into_api: false" in markdown
    assert '"sample_id": "one"' in paths["predictions"].read_text(encoding="utf-8")


def test_notebook_has_standalone_phase1g_kernel_cell():
    notebook = json.loads(
        Path("notebooks/phase1_layoutlmv3_training.ipynb").read_text(encoding="utf-8")
    )
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    source = next(text for text in sources if "require_phase1g_paths" in text)

    assert "sys.executable" in source
    assert "resolve_project_root" in source
    assert "build_phase1g_paths(PROJECT_ROOT)" in source
    assert "require_phase1g_paths" in source
    assert 'script_path = PROJECT_ROOT / "scripts" / "phase1"' in source
    assert "str(script_path)" in source
    assert "--image-root" in source
    assert 'print(f"image_root={paths.image_root}")' in source
    assert "PROJECT_ROOT = Path.cwd" not in source
    assert "train_one_epoch" not in source
    assert "check=True" in source
