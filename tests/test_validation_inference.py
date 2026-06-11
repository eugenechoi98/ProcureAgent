"""Phase 1G checkpoint inference 与日期重建对比测试。"""

from pathlib import Path
import json

import pytest

from procureguard.extraction.schemas import OCRToken, SroieSample
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
    source = next(text for text in sources if "compare_date_reconstruction.py" in text)

    assert "sys.executable" in source
    assert "--image-root" in source
    assert "train_one_epoch" not in source
    assert "check=True" in source
