"""Phase 1A OCR baseline 与 SROIE 最小闭环测试。"""

from pathlib import Path
import json

import pytest

from procureguard.extraction.alignment import BIO_LABELS, LABEL2ID, align_sample_tokens, align_samples
from procureguard.extraction.baseline import SroieRegexBaseline
from procureguard.extraction.datasets import (
    iter_sroie_samples,
    map_sroie_to_procureguard_fields,
    read_processed_jsonl,
    write_processed_jsonl,
)
from procureguard.extraction.error_analysis import collect_error_cases
from procureguard.extraction.hf_sroie_task3 import (
    convert_task3_row,
    inspect_task3_metadata,
    split_task3_samples,
)
from procureguard.extraction.layoutlmv3_dataset import SROIELayoutLMv3Dataset, create_layoutlmv3_processor
from procureguard.extraction.metrics import evaluate_field_f1
from procureguard.extraction.modelscope_sroie import inspect_modelscope_mirror, organize_modelscope_mirror
from procureguard.extraction.ocr import (
    build_token,
    filter_empty_tokens,
    normalize_bbox,
    paddleocr_result_to_tokens,
    paddleocr_v3_result_to_tokens,
)
from procureguard.extraction.schemas import OCRToken, SroieSample
from procureguard.extraction.training import (
    EpochLog,
    LayoutLMv3TrainingConfig,
    TrainingGuardState,
    build_training_report,
    save_loss_curve,
    select_best_epoch,
    training_report_to_markdown,
    validate_training_guard,
    write_training_outputs,
)


def token(text: str, y: int) -> OCRToken:
    """构造测试 token。"""

    return OCRToken(text=text, bbox=(10, y, 200, y + 20), confidence=1.0)


def test_normalize_bbox_uses_layoutlmv3_coordinate_space():
    bbox = normalize_bbox([[10, 20], [110, 20], [110, 220], [10, 220]], width=200, height=400)

    assert bbox == (50, 50, 550, 550)


def test_normalize_bbox_clips_out_of_bound_coordinates():
    bbox = normalize_bbox([[-10, -20], [250, -20], [250, 500], [-10, 500]], width=200, height=400)

    assert bbox == (0, 0, 1000, 1000)


def test_empty_text_filter_confidence_boundary_and_order_are_stable():
    tokens = filter_empty_tokens(
        [
            build_token(" first ", (0, 0, 10, 10), 0.0),
            build_token("   ", (0, 10, 10, 20), 0.5),
            build_token("second", (0, 20, 10, 30), 1.0),
        ]
    )

    assert [item.text for item in tokens] == ["first", "second"]
    assert [item.confidence for item in tokens] == [0.0, 1.0]
    with pytest.raises(ValueError, match="confidence"):
        OCRToken(text="bad", bbox=(0, 0, 1, 1), confidence=1.1)


def test_paddleocr_result_conversion_without_real_paddleocr():
    result = [
        [
            ([[0, 0], [100, 0], [100, 20], [0, 20]], ("Acme", 0.92)),
            ([[0, 30], [100, 30], [100, 50], [0, 50]], ("", 0.8)),
            ([[0, 60], [100, 60], [100, 80], [0, 80]], ("Total 10.00", 0.88)),
        ]
    ]

    tokens = paddleocr_result_to_tokens(result, width=200, height=100)

    assert [item.text for item in tokens] == ["Acme", "Total 10.00"]
    assert tokens[0].bbox == (0, 0, 500, 200)


def test_regex_baseline_extracts_sroie_fields_and_mapping():
    extracted = SroieRegexBaseline().extract(
        [
            token("Acme Office Supplies", 10),
            token("12 Market Street", 40),
            token("Date 10 Jun 2026", 70),
            token("Subtotal 1,000.00", 100),
            token("Grand Total USD 1,200.00", 130),
        ]
    )

    assert extracted.fields["company"].value == "Acme Office Supplies"
    assert extracted.fields["address"].value == "12 Market Street"
    assert extracted.fields["date"].value == "2026-06-10"
    assert extracted.fields["total"].value == "1200.00"
    assert extracted.to_procureguard_fields() == {
        "vendor_name": "Acme Office Supplies",
        "invoice_date": "2026-06-10",
        "total_amount": 1200.0,
    }


def test_regex_baseline_returns_empty_values_for_missing_fields():
    extracted = SroieRegexBaseline().extract([token("Receipt", 10)])

    assert extracted.fields["total"].value is None
    assert extracted.fields["date"].value is None


def test_regex_baseline_does_not_treat_subtotal_as_grand_total():
    extracted = SroieRegexBaseline().extract(
        [
            token("Acme", 10),
            token("Subtotal 500.00", 40),
            token("Tax 50.00", 70),
        ]
    )

    assert extracted.fields["total"].value is None


def test_sroie_fixture_reader_converter_and_evaluator(tmp_path: Path):
    raw_dir = Path("tests/fixtures/sroie_minimal/raw")
    output = tmp_path / "processed.jsonl"

    samples = iter_sroie_samples(raw_dir)
    write_processed_jsonl(samples, output)
    loaded = read_processed_jsonl(output)
    predictions = [SroieRegexBaseline().extract(sample.tokens).values() for sample in loaded]
    references = [sample.labels for sample in loaded]
    metrics = evaluate_field_f1(predictions, references)
    errors = collect_error_cases([sample.sample_id for sample in loaded], predictions, references)

    assert len(loaded) == 2
    assert output.read_text(encoding="utf-8").count("\n") == 2
    assert any(metric.field == "total" and metric.support == 2 for metric in metrics)
    assert any(error.sample_id == "receipt_error" for error in errors)


def test_sroie_fields_map_to_existing_procureguard_schema_only():
    mapped = map_sroie_to_procureguard_fields(
        {"company": "Acme", "date": "2026-06-10", "address": "Main St", "total": "1200.00"}
    )

    assert mapped == {
        "vendor_name": "Acme",
        "invoice_date": "2026-06-10",
        "total_amount": "1200.00",
    }


def test_bio_label_mapping_is_fixed():
    assert BIO_LABELS == [
        "O",
        "B-COMPANY",
        "I-COMPANY",
        "B-ADDRESS",
        "I-ADDRESS",
        "B-DATE",
        "I-DATE",
        "B-TOTAL",
        "I-TOTAL",
    ]
    assert LABEL2ID["B-COMPANY"] == 1
    assert "B-PO_NUMBER" not in LABEL2ID


def test_alignment_single_and_multi_token_fields():
    sample = SroieSample(
        sample_id="align_ok",
        image_path="missing.jpg",
        tokens=[
            token("Acme", 10),
            token("Office", 20),
            token("12", 30),
            token("Market", 40),
            token("Street", 50),
            token("2026-06-10", 60),
            token("1200.00", 70),
        ],
        labels={
            "company": "Acme Office",
            "address": "12 Market Street",
            "date": "2026-06-10",
            "total": "1200.00",
        },
    )

    labels, unaligned = align_sample_tokens(sample)

    assert labels == [
        "B-COMPANY",
        "I-COMPANY",
        "B-ADDRESS",
        "I-ADDRESS",
        "I-ADDRESS",
        "B-DATE",
        "B-TOTAL",
    ]
    assert unaligned == []
    assert len(labels) == len(sample.tokens)


def test_alignment_repeated_token_is_deterministic_and_normalized():
    sample = SroieSample(
        sample_id="repeat",
        image_path="missing.jpg",
        tokens=[token("ACME", 10), token("acme", 20), token("  1,200.00 ", 30)],
        labels={"company": " acme ", "address": "", "date": "", "total": "1200.00"},
    )

    labels, unaligned = align_sample_tokens(sample)

    assert labels == ["B-COMPANY", "O", "B-TOTAL"]
    assert unaligned == []


def test_alignment_records_unaligned_warning():
    sample = SroieSample(
        sample_id="missing",
        image_path="missing.jpg",
        tokens=[token("Receipt", 10)],
        labels={"company": "Acme", "address": "", "date": "", "total": ""},
    )

    all_labels, summary = align_samples([sample])

    assert all_labels == [["O"]]
    assert summary.total_fields == 1
    assert summary.aligned_fields == 0
    assert summary.unaligned_cases[0].field == "company"


def test_layoutlmv3_dataset_with_fake_processor_outputs_expected_keys():
    class FakeProcessor:
        def __call__(self, image, words, boxes, word_labels, **kwargs):
            max_length = kwargs["max_length"]
            padded_labels = word_labels + [-100] * (max_length - len(word_labels))
            return {
                "input_ids": [[101] + [1] * (max_length - 1)],
                "attention_mask": [[1] * max_length],
                "bbox": [[boxes[0]] * max_length],
                "pixel_values": [[[0]]],
                "labels": [padded_labels],
            }

    sample = SroieSample(
        sample_id="dataset",
        image_path="missing.jpg",
        tokens=[token("Acme", 10), token("Total 10.00", 20)],
        labels={"company": "Acme", "address": "", "date": "", "total": "10.00"},
    )
    dataset = SROIELayoutLMv3Dataset([sample], FakeProcessor(), LABEL2ID, max_length=8)
    item = dataset[0]

    assert set(item) == {"input_ids", "attention_mask", "bbox", "pixel_values", "labels"}
    assert len(item["labels"]) == 8
    assert sum(label != -100 for label in item["labels"]) == 2


def test_layoutlmv3_processor_dependency_error_is_clear(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="extraction"):
        create_layoutlmv3_processor()


def test_modelscope_mirror_inspection_and_idempotent_organization(tmp_path: Path):
    source = tmp_path / "mirror"
    for split in ["training", "test"]:
        (source / "imgs" / split).mkdir(parents=True)
        (source / "annotations" / split).mkdir(parents=True)
        (source / "imgs" / split / f"{split}_1.jpg").write_bytes(b"image")
        (source / "annotations" / split / f"{split}_1.txt").write_text(
            "0,0,10,0,10,10,0,10,Acme\n", encoding="utf-8"
        )
    for name, split in [("train_label.jsonl", "training"), ("test_label.jsonl", "test")]:
        (source / name).write_text(
            json.dumps({"filename": f"{split}/{split}_1_1.png", "text": "Acme"}) + "\n",
            encoding="utf-8",
        )
    for name, split in [("instances_training.json", "training"), ("instances_test.json", "test")]:
        (source / name).write_text(
            json.dumps({"images": [{"file_name": f"{split}_1.jpg"}], "annotations": [], "categories": []}),
            encoding="utf-8",
        )

    inspection = inspect_modelscope_mirror(source)
    first = organize_modelscope_mirror(source, tmp_path / "raw")
    second = organize_modelscope_mirror(source, tmp_path / "raw")

    assert inspection["contains_entity_fields"] is False
    assert first.copied_images == 2
    assert first.copied_boxes == 2
    assert first.copied_keys == 0
    assert second.skipped_existing == 4
    assert first.train.instance_image_count == 1


def test_unlabeled_sroie_can_be_prepared_without_fake_ground_truth(tmp_path: Path):
    raw = tmp_path / "raw"
    (raw / "img").mkdir(parents=True)
    (raw / "box").mkdir()
    (raw / "key").mkdir()
    (raw / "box" / "sample.txt").write_text(
        "0,0,10,0,10,10,0,10,Acme\n", encoding="utf-8"
    )

    samples, errors = iter_sroie_samples(raw, strict=False, allow_missing_labels=True)

    assert errors == []
    assert len(samples) == 1
    assert samples[0].labels == {"company": "", "address": "", "date": "", "total": ""}


def build_task3_row(sample_id: str = "sample-1") -> dict:
    """构造离线 Task 3 fixture。"""

    return {
        "_id": {"$oid": sample_id},
        "filepath": f"data/{sample_id}.jpg",
        "metadata": {"width": 200, "height": 100},
        "company": "Acme Office",
        "address": "12 Market Street",
        "date": "2026-06-10",
        "total": "$1,200.00",
        "text_detections": {
            "detections": [
                {"label": "Acme Office", "bounding_box": [0.1, 0.1, 0.4, 0.1]},
                {"label": "12 Market Street", "bounding_box": [0.1, 0.3, 0.5, 0.1]},
                {"label": "2026-06-10", "bounding_box": [0.1, 0.5, 0.3, 0.1]},
                {"label": "TOTAL $1,200.00", "bounding_box": [0.1, 0.7, 0.5, 0.1]},
            ]
        },
        "text_polygons": {"polylines": []},
    }


def test_task3_adapter_metadata_bbox_and_fields(tmp_path: Path):
    row = build_task3_row()
    samples_path = tmp_path / "samples.json"
    samples_path.write_text(json.dumps({"samples": [row]}), encoding="utf-8")

    summary = inspect_task3_metadata(samples_path)
    sample = convert_task3_row(row, tmp_path)
    labels, unaligned = align_sample_tokens(sample)

    assert summary.sample_count == 1
    assert summary.missing_fields == {"company": 0, "address": 0, "date": 0, "total": 0}
    assert sample.tokens[0].bbox == (100, 100, 500, 200)
    assert sample.labels["company"] == "Acme Office"
    assert any(label != "O" for label in labels)
    assert unaligned == []


def test_task3_split_seed_is_stable_and_disjoint(tmp_path: Path):
    samples = [convert_task3_row(build_task3_row(f"sample-{index}"), tmp_path) for index in range(10)]

    first = split_task3_samples(samples, seed=42)
    second = split_task3_samples(samples, seed=42)
    train_ids = {sample.sample_id for sample in first.train}
    validation_ids = {sample.sample_id for sample in first.validation}

    assert [sample.sample_id for sample in first.train] == [sample.sample_id for sample in second.train]
    assert train_ids.isdisjoint(validation_ids)
    assert len(first.train) == 8
    assert len(first.validation) == 2


def test_paddleocr_v3_result_conversion():
    result = [
        {
            "rec_texts": ["Acme", ""],
            "rec_scores": [0.91, 0.8],
            "rec_polys": [
                [[0, 0], [100, 0], [100, 20], [0, 20]],
                [[0, 30], [100, 30], [100, 50], [0, 50]],
            ],
        }
    ]

    tokens = paddleocr_v3_result_to_tokens(result, width=200, height=100)

    assert len(tokens) == 1
    assert tokens[0].text == "Acme"
    assert tokens[0].confidence == 0.91


def test_training_config_defaults():
    config = LayoutLMv3TrainingConfig()

    assert config.model_name == "microsoft/layoutlmv3-base"
    assert config.max_length == 512
    assert config.batch_size == 2
    assert config.gradient_accumulation_steps == 4
    assert config.epochs == 5
    assert config.learning_rate == 1e-5
    assert config.weight_decay == 0.01
    assert config.max_grad_norm == 1.0
    assert config.seed == 42


def test_training_guard_accepts_ready_state_and_rejects_cpu():
    validate_training_guard(
        TrainingGuardState(
            cuda_available=True,
            train_samples=570,
            validation_samples=142,
            labels_non_o_count=6,
            baseline_report_exists=True,
        )
    )

    with pytest.raises(RuntimeError, match="cuda_available"):
        validate_training_guard(
            TrainingGuardState(
                cuda_available=False,
                train_samples=570,
                validation_samples=142,
                labels_non_o_count=6,
                baseline_report_exists=True,
            )
        )


def sample_epoch_logs() -> list[EpochLog]:
    """构造训练日志 fixture。"""

    return [
        EpochLog(1, 1.2, 1.1, 0.50, 0.48, 1e-5, 60.0),
        EpochLog(2, 0.9, 0.8, 0.65, 0.62, 8e-6, 62.0),
        EpochLog(3, 0.7, 0.9, 0.68, 0.62, 6e-6, 61.0),
    ]


def test_epoch_log_schema_best_epoch_and_report_format():
    logs = sample_epoch_logs()
    best = select_best_epoch(logs)
    report = build_training_report(
        config=LayoutLMv3TrainingConfig(epochs=3),
        logs=logs,
        baseline_macro_f1=0.4387,
    )
    markdown = training_report_to_markdown(report)

    assert set(logs[0].__dict__) == {
        "epoch",
        "train_loss",
        "validation_loss",
        "token_f1",
        "field_macro_f1",
        "learning_rate",
        "elapsed_time",
    }
    assert best.epoch == 2
    assert report["best_epoch"] == 2
    assert report["improvement"] == pytest.approx(0.1813)
    assert "local_validation_split_seed_42" in markdown
    assert "baseline_macro_f1: 0.4387" in markdown


def test_loss_curve_output_function_without_matplotlib(tmp_path: Path):
    output = tmp_path / "loss.png"

    def fake_plotter(logs, path):
        assert len(logs) == 3
        path.write_bytes(b"png")

    result = save_loss_curve(sample_epoch_logs(), output, plotter=fake_plotter)

    assert result == output
    assert output.read_bytes() == b"png"


def test_training_outputs_write_json_csv_and_markdown(tmp_path: Path):
    report = build_training_report(
        config=LayoutLMv3TrainingConfig(epochs=3),
        logs=sample_epoch_logs(),
        baseline_macro_f1=0.4387,
    )

    paths = write_training_outputs(report, tmp_path)

    assert set(paths) == {"json", "csv", "markdown"}
    assert all(path.exists() for path in paths.values())
    assert "field_macro_f1" in paths["csv"].read_text(encoding="utf-8")
    assert "fine_tuned_macro_f1" in paths["markdown"].read_text(encoding="utf-8")
