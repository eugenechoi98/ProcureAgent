"""Phase 1A OCR baseline 与 SROIE 最小闭环测试。"""

from pathlib import Path

import pytest

from procureguard.extraction.baseline import SroieRegexBaseline
from procureguard.extraction.datasets import (
    iter_sroie_samples,
    map_sroie_to_procureguard_fields,
    read_processed_jsonl,
    write_processed_jsonl,
)
from procureguard.extraction.error_analysis import collect_error_cases
from procureguard.extraction.metrics import evaluate_field_f1
from procureguard.extraction.ocr import build_token, filter_empty_tokens, normalize_bbox, paddleocr_result_to_tokens
from procureguard.extraction.schemas import OCRToken


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
