"""首轮 GPU 结果、日期分析与 hybrid 评测测试。"""

import json
from pathlib import Path

import pytest

from procureguard.extraction.gpu_notebook import require_safetensors_model
from procureguard.extraction.field_reconstruction import reconstruct_bio_fields
from procureguard.extraction.phase1_results import (
    analyze_date_validation,
    date_analysis_to_markdown,
    first_gpu_training_report,
    hybrid_metrics,
    hybrid_report_to_markdown,
)
from procureguard.extraction.schemas import OCRToken, SroieSample


def sample(
    sample_id: str,
    date: str,
    token_texts: list[str],
) -> SroieSample:
    """构造日期分析 fixture。"""

    return SroieSample(
        sample_id=sample_id,
        image_path=f"{sample_id}.jpg",
        tokens=[
            OCRToken(text=text, bbox=(0, index * 10, 100, index * 10 + 8))
            for index, text in enumerate(token_texts)
        ],
        labels={"company": "", "address": "", "date": date, "total": ""},
    )


def test_safetensors_is_required_and_bin_does_not_fallback(tmp_path: Path):
    model_dir = tmp_path / "layoutlmv3-base"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"legacy")

    with pytest.raises(FileNotFoundError, match="Do not fall back"):
        require_safetensors_model(model_dir)

    expected = model_dir / "model.safetensors"
    expected.write_bytes(b"safe")
    assert require_safetensors_model(model_dir) == expected.resolve()


def test_first_gpu_report_contains_real_metrics_and_split():
    report = first_gpu_training_report()

    assert report["gpu"] == "NVIDIA A10"
    assert report["best_epoch"] == 5
    assert report["fine_tuned_macro_f1"] == pytest.approx(0.6231337901)
    assert report["evaluation_split"] == "local_validation_split_seed_42"
    assert report["official_test"] is False
    assert len(report["epoch_logs"]) == 5


def test_date_analysis_fixture_and_report_format():
    samples = [
        sample("exact", "30-04-2018", ["DATE", "30-04-2018"]),
        sample("multiple", "20/06/2018", ["18/06/2020", "20/06/2018"]),
        sample("missing", "01-NOV-2017", ["NO DATE"]),
    ]

    report = analyze_date_validation(samples)
    markdown = date_analysis_to_markdown(report)

    assert report["sample_count"] == 3
    assert report["observable_evidence_counts"]["ocr_missing"] == 1
    assert report["observable_evidence_counts"]["multiple_date_candidates"] == 1
    assert "prediction_format_distribution" in report
    assert "unavailable_without_cloud_prediction_details" in markdown
    assert "model_classification_miss" in markdown


def test_date_field_reconstruction_removes_prefix_and_time():
    tokens = [
        OCRToken("DATE:", (0, 0, 50, 10)),
        OCRToken("30-04-2018", (51, 0, 120, 10)),
        OCRToken("19:50:14", (121, 0, 180, 10)),
    ]

    fields = reconstruct_bio_fields(
        tokens,
        ["B-DATE", "I-DATE", "I-DATE"],
    )

    assert fields["date"] == "2018-04-30"


def test_hybrid_extraction_metrics_and_markdown():
    rows = hybrid_metrics()
    macro = next(row for row in rows if row["field"] == "macro")
    markdown = hybrid_report_to_markdown(rows)

    assert macro["hybrid_f1"] == pytest.approx(0.79487033896)
    assert macro["hybrid_f1"] > macro["layoutlmv3_f1"]
    assert macro["hybrid_f1"] > macro["baseline_f1"]
    assert "company/address/total=LayoutLMv3" in markdown
    assert "| macro | 0.4387 | 0.6231 | 0.7949 |" in markdown


def test_notebook_forces_safetensors_and_disables_tokenizer_parallelism():
    notebook = json.loads(
        Path("notebooks/phase1_layoutlmv3_training.ipynb").read_text(encoding="utf-8")
    )
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert 'os.environ["TOKENIZERS_PARALLELISM"] = "false"' in text
    assert text.count("use_safetensors=True") >= 2
    assert "pytorch_model.bin" not in text
