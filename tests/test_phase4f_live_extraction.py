"""Phase 4F 本地 live extraction spike 契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
import pytest

from procureguard.extraction.alignment import ID2LABEL
from procureguard.extraction.live_spike import (
    LiveExtractionFailure,
    check_live_extraction_assets,
    run_live_extraction,
    write_failure,
)
from procureguard.extraction.schemas import OCRToken


def make_checkpoint(path: Path) -> Path:
    """创建不含真实权重的最小资产检查 fixture。"""

    path.mkdir()
    (path / "model.safetensors").write_bytes(b"test-fixture-not-a-real-model")
    (path / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (path / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (path / "config.json").write_text(
        json.dumps({"id2label": {str(key): value for key, value in ID2LABEL.items()}}),
        encoding="utf-8",
    )
    (path / "label_map.json").write_text(
        json.dumps(
            {
                "id2label": {str(key): value for key, value in ID2LABEL.items()},
                "label2id": {value: key for key, value in ID2LABEL.items()},
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeOCR:
    """返回固定 token，测试不初始化 PaddleOCR 或下载资产。"""

    def extract_tokens(self, _image: Path) -> list[OCRToken]:
        return [
            OCRToken("ACME", (10, 10, 200, 60), 0.99),
            OCRToken("2026-06-15", (10, 80, 240, 130), 0.98),
            OCRToken("1200.00", (600, 800, 900, 860), 0.97),
        ]


def fake_inference(**kwargs) -> tuple[list[str], list[float]]:
    """模拟 word-level 模型输出，不生成风险字段。"""

    assert kwargs["tokens"]
    return ["B-COMPANY", "B-DATE", "B-TOTAL"], [0.91, 0.88, 0.95]


def test_asset_check_fails_clearly_without_checkpoint(tmp_path: Path) -> None:
    summary = check_live_extraction_assets(tmp_path / "missing")

    assert summary["status"] is False
    assert summary["download_attempted"] is False
    assert "missing_checkpoint" in summary["failure_codes"]
    assert "missing_processor" in summary["failure_codes"]
    assert "missing_label_map" in summary["failure_codes"]


def test_asset_check_does_not_load_or_download_model(tmp_path: Path, monkeypatch) -> None:
    checkpoint = make_checkpoint(tmp_path / "checkpoint")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("from_pretrained must not run during asset check")

    monkeypatch.setattr("transformers.LayoutLMv3Processor.from_pretrained", forbidden)
    summary = check_live_extraction_assets(checkpoint)

    assert summary["download_attempted"] is False


def test_asset_check_reports_missing_ocr_dependency(tmp_path: Path, monkeypatch) -> None:
    checkpoint = make_checkpoint(tmp_path / "checkpoint")
    original = __import__("importlib.util", fromlist=["find_spec"]).find_spec

    def fake_find_spec(name: str):
        return None if name in {"paddle", "paddleocr"} else original(name)

    monkeypatch.setattr("procureguard.extraction.live_spike.importlib.util.find_spec", fake_find_spec)
    summary = check_live_extraction_assets(checkpoint)

    assert summary["status"] is False
    assert "ocr_dependency_missing" in summary["failure_codes"]
    assert "pip install" in summary["install_hint"]


def test_asset_check_rejects_label_count_or_order_mismatch(tmp_path: Path) -> None:
    checkpoint = make_checkpoint(tmp_path / "checkpoint")
    (checkpoint / "label_map.json").write_text(
        json.dumps({"id2label": {"0": "O"}, "label2id": {"O": 0}}),
        encoding="utf-8",
    )

    summary = check_live_extraction_assets(checkpoint)

    assert summary["status"] is False
    assert "missing_label_map" in summary["failure_codes"]
    assert summary["label_map"]["model_label_count"] == 9
    assert summary["label_map"]["bundle_label_count"] == 1


def test_invalid_image_writes_parseable_failure_json(tmp_path: Path) -> None:
    output = tmp_path / "output"
    with pytest.raises(LiveExtractionFailure) as caught:
        run_live_extraction(tmp_path / "missing.png", output)

    payload = write_failure(output, caught.value)
    saved = json.loads((output / "extraction_failure.json").read_text(encoding="utf-8"))
    assert payload["failure_code"] == "image_file_invalid"
    assert saved["status"] is False
    assert saved["fake_prediction_generated"] is False
    assert saved["phase2_invoked"] is False


def test_fake_runtime_outputs_parseable_field_candidate_schema(tmp_path: Path) -> None:
    checkpoint = make_checkpoint(tmp_path / "checkpoint")
    image = tmp_path / "invoice.png"
    Image.new("RGB", (1000, 1000), "white").save(image)
    output = tmp_path / "output"

    result = run_live_extraction(
        image,
        output,
        checkpoint=checkpoint,
        ocr_factory=FakeOCR,
        inference_runner=fake_inference,
    )
    payload = json.loads(
        (output / "layoutlmv3_field_candidates.json").read_text(encoding="utf-8")
    )

    assert result["status"] is True
    assert payload["phase2_invoked"] is False
    assert payload["risk_decision_generated"] is False
    assert {item["field_name"] for item in payload["fields"]} == {
        "company", "address", "date", "total"
    }
    assert all(item["source"] == "live_layoutlmv3" for item in payload["fields"])
    assert all(item["requires_human_confirmation"] is True for item in payload["fields"])
    assert not _contains_key(payload, "risk_level")
    assert not _contains_key(payload, "recommended_action")
    assert json.loads((output / "ocr_tokens.json").read_text(encoding="utf-8"))["token_count"] == 3
    assert (output / "extraction_report.md").is_file()
    assert (output / "environment_summary.json").is_file()


def test_spike_source_has_no_phase2_audit_dependency() -> None:
    source = Path("procureguard/extraction/live_spike.py").read_text(encoding="utf-8")

    assert "AgentInvoiceProcessor" not in source
    assert "run_manual_audit" not in source
    assert "risk_level" not in source
    assert "recommended_action" not in source


def test_phase4f_uses_only_public_or_synthetic_sample_guidance() -> None:
    source = Path("docs/phase4f_local_live_extraction_spike.md")
    if source.exists():
        text = source.read_text(encoding="utf-8")
        assert "真实敏感发票" in text
        assert "SROIE" in text


def _contains_key(value, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False
