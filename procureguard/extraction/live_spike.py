"""Phase 4F 本地 OCR 与 LayoutLMv3 字段候选 spike。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import platform
import time
from typing import Any, Callable

from procureguard.extraction.alignment import BIO_LABELS
from procureguard.extraction.field_reconstruction import reconstruct_bio_fields
from procureguard.extraction.schemas import OCRToken, SROIE_FIELDS, SroieSample


DEFAULT_CHECKPOINT = Path("checkpoints/phase1/layoutlmv3_best")
PROCESSOR_REQUIRED = ("preprocessor_config.json", "tokenizer_config.json")
TOKENIZER_FILE_GROUPS = (("tokenizer.json",), ("vocab.json", "merges.txt"))
UNSAFE_WEIGHT_SUFFIXES = (".bin", ".pt", ".pth", ".ckpt")
FAILURE_CODES = {
    "missing_checkpoint",
    "missing_processor",
    "missing_label_map",
    "ocr_dependency_missing",
    "ocr_no_tokens",
    "image_file_invalid",
    "layoutlmv3_inference_failed",
    "field_reconstruction_failed",
    "unsupported_runtime",
    "no_cuda_and_cpu_disabled",
}


class LiveExtractionFailure(RuntimeError):
    """携带稳定失败码的本地 extraction 异常。"""

    def __init__(self, code: str, message: str, remediation: str):
        if code not in FAILURE_CODES:
            raise ValueError(f"Unsupported live extraction failure code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def check_live_extraction_assets(
    checkpoint: str | Path = DEFAULT_CHECKPOINT,
    *,
    processor: str | Path | None = None,
    label_map: str | Path | None = None,
    sample_image: str | Path | None = None,
    cpu_allowed: bool = True,
) -> dict[str, Any]:
    """只读检查本地 checkpoint、processor、label map 和运行依赖。"""

    checkpoint_path = Path(checkpoint).expanduser().resolve()
    processor_path = Path(processor).expanduser().resolve() if processor else checkpoint_path
    checkpoint_exists = checkpoint_path.is_dir()
    safetensors = sorted(path.name for path in checkpoint_path.glob("*.safetensors"))
    unsafe_weights = sorted(
        path.name
        for path in checkpoint_path.iterdir()
        if checkpoint_exists and path.is_file() and path.suffix.lower() in UNSAFE_WEIGHT_SUFFIXES
    ) if checkpoint_exists else []
    processor_missing = [
        name for name in PROCESSOR_REQUIRED if not (processor_path / name).is_file()
    ]
    tokenizer_ready = any(
        all((processor_path / name).is_file() for name in group)
        for group in TOKENIZER_FILE_GROUPS
    )
    if not tokenizer_ready:
        processor_missing.append("tokenizer.json or vocab.json+merges.txt")

    config_path = checkpoint_path / "config.json"
    label_map_path = (
        Path(label_map).expanduser().resolve()
        if label_map
        else checkpoint_path / "label_map.json"
    )
    label_map_valid = False
    label_map_error = None
    label_map_payload = None
    config_labels: list[str] = []
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            raw_config_labels = config.get("id2label", {})
            config_labels = [
                str(raw_config_labels[str(index)] if str(index) in raw_config_labels else raw_config_labels[index])
                for index in range(len(raw_config_labels))
            ]
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            label_map_error = f"config.json is not readable JSON: {exc}"
    else:
        label_map_error = "config.json is missing"
    if label_map_path.is_file():
        try:
            label_map_payload = json.loads(label_map_path.read_text(encoding="utf-8"))
            raw_id2label = label_map_payload.get("id2label", {})
            bundle_labels = [
                str(raw_id2label[str(index)] if str(index) in raw_id2label else raw_id2label[index])
                for index in range(len(raw_id2label))
            ]
            expected = list(BIO_LABELS)
            label_map_valid = bundle_labels == expected and config_labels == expected
            if not label_map_valid:
                label_map_error = (
                    "label_map.json and model config label order must both match the nine Phase 1 BIO labels"
                )
        except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
            label_map_error = f"label_map.json is invalid: {exc}"
    elif label_map_error is None:
        label_map_error = "label_map.json is missing"

    sample_path = Path(sample_image).expanduser().resolve() if sample_image else None
    sample_ready = sample_path.is_file() if sample_path else None

    dependencies = {
        name: importlib.util.find_spec(name) is not None
        for name in ("PIL", "paddle", "paddleocr", "torch", "transformers")
    }
    cuda_available = False
    if dependencies["torch"]:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            dependencies["torch"] = False

    failures = []
    if not checkpoint_exists or not safetensors:
        failures.append("missing_checkpoint")
    if processor_missing:
        failures.append("missing_processor")
    if not label_map_valid:
        failures.append("missing_label_map")
    if not dependencies["paddleocr"] or not dependencies["paddle"]:
        failures.append("ocr_dependency_missing")
    if not dependencies["PIL"] or not dependencies["torch"] or not dependencies["transformers"]:
        failures.append("unsupported_runtime")
    if not cuda_available and not cpu_allowed:
        failures.append("no_cuda_and_cpu_disabled")

    return {
        "status": not failures,
        "checked_at": _now_iso(),
        "download_attempted": False,
        "checkpoint": {
            "path": str(checkpoint_path),
            "directory_exists": checkpoint_exists,
            "safetensors_files": safetensors,
            "safe_format_only": bool(safetensors) and not unsafe_weights,
            "unsafe_weight_files": unsafe_weights,
        },
        "processor": {
            "path": str(processor_path),
            "missing_files": processor_missing,
            "ready": not processor_missing,
        },
        "label_map": {
            "path": str(label_map_path),
            "model_config": str(config_path),
            "valid": label_map_valid,
            "error": label_map_error,
            "expected_labels": BIO_LABELS,
            "model_label_count": len(config_labels),
            "bundle_label_count": len(label_map_payload.get("id2label", {})) if label_map_payload else 0,
        },
        "sample_image": {
            "path": str(sample_path) if sample_path else None,
            "exists": sample_ready,
        },
        "dependencies": dependencies,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cuda_available": cuda_available,
            "cpu_allowed": cpu_allowed,
            "device_plan": "cuda" if cuda_available else ("cpu" if cpu_allowed else "blocked"),
            "notice": "no_cuda_but_cpu_allowed" if not cuda_available and cpu_allowed else None,
        },
        "failure_codes": failures,
        "install_hint": '.\\.venv\\Scripts\\python.exe -m pip install -e ".[extraction]"',
    }


def run_live_extraction(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    checkpoint: str | Path = DEFAULT_CHECKPOINT,
    processor: str | Path | None = None,
    label_map: str | Path | None = None,
    cpu_allowed: bool = True,
    ocr_factory: Callable[[], Any] | None = None,
    inference_runner: Callable[..., tuple[list[str], list[float]]] | None = None,
) -> dict[str, Any]:
    """运行独立 extraction spike，绝不进入 Phase 2。"""

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = _validate_image(image_path)
    assets = check_live_extraction_assets(
        checkpoint,
        processor=processor,
        label_map=label_map,
        sample_image=image,
        cpu_allowed=cpu_allowed,
    )
    _write_json(output / "environment_summary.json", assets)
    if not assets["status"]:
        code = assets["failure_codes"][0]
        raise LiveExtractionFailure(code, _asset_failure_message(code, assets), _remediation(code))

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    started = time.perf_counter()
    try:
        if ocr_factory is None:
            from procureguard.extraction.ocr import PaddleOCRAdapter

            ocr_factory = PaddleOCRAdapter
        tokens = ocr_factory().extract_tokens(image)
    except ImportError as exc:
        raise LiveExtractionFailure(
            "ocr_dependency_missing", str(exc), _remediation("ocr_dependency_missing")
        ) from exc
    except Exception as exc:
        raise LiveExtractionFailure(
            "layoutlmv3_inference_failed",
            f"OCR initialization or execution failed in offline mode: {exc}",
            "Install or pre-provision PaddleOCR model assets locally; this spike does not download them.",
        ) from exc
    if not tokens:
        raise LiveExtractionFailure(
            "ocr_no_tokens",
            "PaddleOCR returned no usable tokens for the image.",
            "Use a clearer supported image and verify the local OCR model assets.",
        )
    _write_json(output / "ocr_tokens.json", _ocr_payload(image, tokens))

    runner = inference_runner or _run_layoutlmv3
    try:
        labels, scores = runner(
            image=image,
            tokens=tokens,
            checkpoint=Path(checkpoint).expanduser().resolve(),
            processor=Path(processor).expanduser().resolve() if processor else Path(checkpoint).expanduser().resolve(),
            cpu_allowed=cpu_allowed,
        )
    except LiveExtractionFailure:
        raise
    except Exception as exc:
        raise LiveExtractionFailure(
            "layoutlmv3_inference_failed",
            f"LayoutLMv3 inference failed: {exc}",
            "Verify the fine-tuned checkpoint, processor files, label map and available memory.",
        ) from exc

    try:
        candidates = _build_field_candidates(tokens, labels, scores)
    except Exception as exc:
        raise LiveExtractionFailure(
            "field_reconstruction_failed",
            f"Field reconstruction failed: {exc}",
            "Verify that word-level BIO labels align with OCR tokens and use the Phase 1 label map.",
        ) from exc

    elapsed = time.perf_counter() - started
    candidate_payload = {
        "status": True,
        "source": "live_layoutlmv3",
        "requires_human_confirmation": True,
        "phase2_invoked": False,
        "risk_decision_generated": False,
        "checkpoint": str(Path(checkpoint).expanduser().resolve()),
        "fields": candidates,
    }
    _write_json(output / "layoutlmv3_field_candidates.json", candidate_payload)
    visualization = _draw_visualization(image, tokens, labels, output / "bbox_visualization.png")
    report = _render_report(image, assets, candidates, elapsed, visualization)
    (output / "extraction_report.md").write_text(report, encoding="utf-8")
    return {
        "status": True,
        "output_dir": str(output),
        "latency_seconds": elapsed,
        "field_count": len(candidates),
        "phase2_invoked": False,
        "risk_decision_generated": False,
        "artifacts": sorted(path.name for path in output.iterdir() if path.is_file()),
    }


def write_failure(output_dir: str | Path, failure: LiveExtractionFailure) -> dict[str, Any]:
    """保存稳定 machine-readable failure contract。"""

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": False,
        "failure_code": failure.code,
        "message": failure.message,
        "remediation": failure.remediation,
        "fake_prediction_generated": False,
        "phase2_invoked": False,
        "risk_decision_generated": False,
        "created_at": _now_iso(),
    }
    _write_json(output / "extraction_failure.json", payload)
    return payload


def _validate_image(path: str | Path) -> Path:
    """验证图片存在且可由 Pillow 解码。"""

    image = Path(path).expanduser().resolve()
    if not image.is_file():
        raise LiveExtractionFailure(
            "image_file_invalid", f"Image file does not exist: {image}", "Provide an existing PNG or JPEG path."
        )
    try:
        from PIL import Image

        with Image.open(image) as loaded:
            loaded.verify()
    except Exception as exc:
        raise LiveExtractionFailure(
            "image_file_invalid", f"Image cannot be decoded: {image}: {exc}", "Use a valid non-sensitive PNG or JPEG image."
        ) from exc
    return image


def _run_layoutlmv3(
    *,
    image: Path,
    tokens: list[OCRToken],
    checkpoint: Path,
    processor: Path,
    cpu_allowed: bool,
) -> tuple[list[str], list[float]]:
    """本地加载 checkpoint 并返回 word-level BIO 标签及真实 softmax 分数。"""

    import torch
    from PIL import Image
    from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor

    if not torch.cuda.is_available() and not cpu_allowed:
        raise LiveExtractionFailure(
            "no_cuda_and_cpu_disabled", "CUDA is unavailable and CPU inference is disabled.", "Enable CPU inference or run on a CUDA host."
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    layout_processor = LayoutLMv3Processor.from_pretrained(
        processor, apply_ocr=False, local_files_only=True
    )
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        checkpoint, local_files_only=True, use_safetensors=True
    ).to(device)
    model.eval()
    with Image.open(image) as loaded:
        encoding = layout_processor(
            loaded.convert("RGB"),
            [token.text for token in tokens],
            boxes=[list(token.bbox) for token in tokens],
            truncation=True,
            padding="max_length",
            max_length=512,
            return_tensors="pt",
        )
    word_ids = encoding.word_ids(batch_index=0)
    tensors = {key: value.to(device) for key, value in encoding.items()}
    with torch.no_grad():
        logits = model(**tensors).logits[0]
        probabilities = torch.softmax(logits, dim=-1)
        predicted = probabilities.argmax(dim=-1)
    id2label = {int(key): value for key, value in model.config.id2label.items()}
    word_results: dict[int, tuple[str, float]] = {}
    for token_index, word_index in enumerate(word_ids):
        if word_index is None or word_index in word_results:
            continue
        label_id = int(predicted[token_index].item())
        word_results[word_index] = (
            id2label[label_id],
            float(probabilities[token_index, label_id].item()),
        )
    labels = [word_results.get(index, ("O", 0.0))[0] for index in range(len(tokens))]
    scores = [word_results.get(index, ("O", 0.0))[1] for index in range(len(tokens))]
    return labels, scores


def _build_field_candidates(
    tokens: list[OCRToken], labels: list[str], scores: list[float]
) -> list[dict[str, Any]]:
    """把 word-level BIO 结果转换为可人工确认的字段候选。"""

    if len(tokens) != len(labels) or len(tokens) != len(scores):
        raise ValueError("OCR tokens, BIO labels and scores must have the same length.")
    values = reconstruct_bio_fields(tokens, labels)
    candidates = []
    for field_name in SROIE_FIELDS:
        indexes = [
            index
            for index, label in enumerate(labels)
            if label.endswith(f"-{field_name.upper()}")
        ]
        spans = _contiguous_spans(indexes)
        confidence = sum(scores[index] for index in indexes) / len(indexes) if indexes else None
        warning = None if values[field_name] else "No field span was predicted; human input is required."
        candidates.append(
            {
                "field_name": field_name,
                "predicted_value": values[field_name] or None,
                "confidence": confidence,
                "confidence_type": "mean_word_label_softmax" if confidence is not None else "unavailable_no_predicted_span",
                "token_spans": spans,
                "bbox_list": [list(tokens[index].bbox) for index in indexes],
                "source": "live_layoutlmv3",
                "requires_human_confirmation": True,
                "warning": warning,
                "failure_reason": None,
            }
        )
    return candidates


def _contiguous_spans(indexes: list[int]) -> list[dict[str, Any]]:
    """把字段 token index 压缩成可追溯连续区间。"""

    if not indexes:
        return []
    groups = [[indexes[0]]]
    for index in indexes[1:]:
        if index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return [{"start": group[0], "end": group[-1]} for group in groups]


def _ocr_payload(image: Path, tokens: list[OCRToken]) -> dict[str, Any]:
    return {
        "status": True,
        "source": "live_paddleocr",
        "image": str(image),
        "token_count": len(tokens),
        "tokens": [asdict(token) for token in tokens],
    }


def _draw_visualization(
    image: Path, tokens: list[OCRToken], labels: list[str], output: Path
) -> bool:
    """绘制 OCR bbox 与预测标签，失败不影响结构化结果。"""

    try:
        from PIL import Image, ImageDraw

        with Image.open(image) as loaded:
            canvas = loaded.convert("RGB")
        draw = ImageDraw.Draw(canvas)
        width, height = canvas.size
        for token, label in zip(tokens, labels, strict=True):
            x0, y0, x1, y1 = token.bbox
            box = (x0 * width // 1000, y0 * height // 1000, x1 * width // 1000, y1 * height // 1000)
            color = "#d62728" if label != "O" else "#0072B2"
            draw.rectangle(box, outline=color, width=2)
            if label != "O":
                draw.text((box[0], max(0, box[1] - 12)), label, fill=color)
        canvas.save(output)
        return True
    except Exception:
        return False


def _render_report(
    image: Path,
    assets: dict[str, Any],
    candidates: list[dict[str, Any]],
    latency: float,
    visualization: bool,
) -> str:
    rows = [
        f"| {item['field_name']} | {item['predicted_value'] or ''} | "
        f"{item['confidence'] if item['confidence'] is not None else 'n/a'} | yes |"
        for item in candidates
    ]
    return "\n".join(
        [
            "# Local Live OCR / LayoutLMv3 Extraction Report",
            "",
            f"- image: `{image}`",
            f"- checkpoint: `{assets['checkpoint']['path']}`",
            f"- device plan: `{assets['runtime']['device_plan']}`",
            f"- latency_seconds: `{latency:.4f}`",
            f"- bbox_visualization_generated: `{str(visualization).lower()}`",
            "- phase2_invoked: `false`",
            "- risk_decision_generated: `false`",
            "- official_test: `false`",
            "",
            "| field | predicted value | confidence | human confirmation required |",
            "|---|---|---:|---|",
            *rows,
            "",
            "This local spike does not prove enterprise-invoice generalization. OCR or extraction errors must not be treated as procurement anomalies. Confirm or correct every field before any future Phase 2 integration.",
            "",
        ]
    )


def _asset_failure_message(code: str, assets: dict[str, Any]) -> str:
    details = {
        "missing_checkpoint": f"Fine-tuned Safetensors checkpoint is missing: {assets['checkpoint']['path']}",
        "missing_processor": f"Processor files are incomplete: {assets['processor']['missing_files']}",
        "missing_label_map": f"Phase 1 BIO label map is unavailable: {assets['label_map']['error']}",
        "ocr_dependency_missing": "PaddleOCR or PaddlePaddle is not importable in the project environment.",
        "unsupported_runtime": "Pillow, Torch or Transformers is not importable in the project environment.",
        "no_cuda_and_cpu_disabled": "CUDA is unavailable and CPU inference is disabled.",
    }
    return details[code]


def _remediation(code: str) -> str:
    hints = {
        "missing_checkpoint": "Place the externally obtained Phase 1 fine-tuned checkpoint under checkpoints/phase1/layoutlmv3_best; do not substitute the base model.",
        "missing_processor": "Copy the processor files saved with the fine-tuned checkpoint into the configured processor directory.",
        "missing_label_map": "Use the fine-tuned checkpoint config.json containing the nine Phase 1 BIO labels.",
        "ocr_dependency_missing": 'Run .\\.venv\\Scripts\\python.exe -m pip install -e ".[extraction]" and provision OCR model assets locally.',
        "unsupported_runtime": 'Run .\\.venv\\Scripts\\python.exe -m pip install -e ".[extraction]".',
        "no_cuda_and_cpu_disabled": "Enable CPU inference or use a CUDA environment.",
    }
    return hints[code]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
