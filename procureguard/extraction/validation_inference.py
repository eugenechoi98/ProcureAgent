"""使用现有 LayoutLMv3 checkpoint 比较旧版与新版字段重建。"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any, Callable

from procureguard.extraction.alignment import ID2LABEL
from procureguard.extraction.field_reconstruction import reconstruct_bio_fields
from procureguard.extraction.gpu_notebook import build_image_indexes, resolve_image_path
from procureguard.extraction.metrics import evaluate_field_f1
from procureguard.extraction.phase1_results import BASELINE_F1
from procureguard.extraction.schemas import OCRToken, SroieSample


def reconstruct_bio_fields_legacy(
    tokens: list[OCRToken],
    labels: list[str],
) -> dict[str, str]:
    """复现首轮 GPU 评测使用的原始字段拼接逻辑。"""

    fields = {"company": "", "address": "", "date": "", "total": ""}
    active_field: str | None = None
    for token, label in zip(tokens, labels, strict=True):
        if label == "O":
            active_field = None
            continue
        prefix, field_name = label.split("-", 1)
        field_name = field_name.lower()
        if prefix == "B":
            fields[field_name] = token.text
            active_field = field_name
        elif prefix == "I" and active_field == field_name:
            fields[field_name] = f"{fields[field_name]} {token.text}".strip()
    return fields


def word_labels_from_predictions(
    predicted_ids: list[int],
    word_ids: list[int | None],
    *,
    id2label: dict[int, str] | None = None,
    word_count: int,
) -> list[str]:
    """把 subword 预测还原为每个 OCR word 的首个 BIO 标签。"""

    labels = id2label or ID2LABEL
    word_predictions: dict[int, str] = {}
    for token_index, word_index in enumerate(word_ids):
        if word_index is not None and word_index not in word_predictions:
            word_predictions[word_index] = labels[int(predicted_ids[token_index])]
    return [word_predictions.get(index, "O") for index in range(word_count)]


def predict_sample_labels(
    sample: SroieSample,
    *,
    processor: Any,
    model: Any,
    torch_module: Any,
    device: Any,
    max_length: int = 512,
    image_loader: Callable[[str], Any] | None = None,
) -> list[str]:
    """对单个 validation 样本执行 checkpoint inference。"""

    if image_loader is None:
        from PIL import Image

        image_loader = lambda path: Image.open(path).convert("RGB")
    image = image_loader(sample.image_path)
    encoding = processor(
        image,
        [token.text for token in sample.tokens],
        boxes=[list(token.bbox) for token in sample.tokens],
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )
    word_ids = encoding.word_ids(batch_index=0)
    tensors = {key: value.to(device) for key, value in encoding.items()}
    with torch_module.no_grad():
        predicted_ids = model(**tensors).logits.argmax(dim=-1)[0].tolist()
    model_id2label = {
        int(index): label for index, label in getattr(model.config, "id2label", ID2LABEL).items()
    }
    return word_labels_from_predictions(
        predicted_ids,
        word_ids,
        id2label=model_id2label,
        word_count=len(sample.tokens),
    )


def resolve_sample_images(
    samples: list[SroieSample],
    image_root: str | Path,
) -> list[SroieSample]:
    """只在内存中解析跨平台图片路径，不改写 processed JSONL。"""

    exact_index, normalized_index = build_image_indexes(image_root)
    resolved_samples = []
    failures = []
    for sample in samples:
        resolved, candidates = resolve_image_path(
            sample.image_path,
            exact_index,
            normalized_index,
        )
        if resolved is None:
            detail = ", ".join(str(path) for path in candidates[:3]) or "no candidates"
            failures.append(f"{sample.sample_id}: {detail}")
            continue
        resolved_samples.append(replace(sample, image_path=str(resolved)))
    if failures:
        preview = "\n".join(failures[:10])
        raise FileNotFoundError(
            f"Unable to resolve {len(failures)} validation images under {image_root}:\n{preview}"
        )
    return resolved_samples


def compare_reconstruction(
    samples: list[SroieSample],
    predicted_labels: list[list[str]],
) -> dict[str, object]:
    """使用同一批 token predictions 对比旧/新重建，隔离后处理变量。"""

    if len(samples) != len(predicted_labels):
        raise ValueError("Samples and predicted labels must have the same length.")
    legacy_predictions = []
    cleaned_predictions = []
    rows = []
    for sample, labels in zip(samples, predicted_labels, strict=True):
        legacy = reconstruct_bio_fields_legacy(sample.tokens, labels)
        cleaned = reconstruct_bio_fields(sample.tokens, labels)
        legacy_predictions.append(legacy)
        cleaned_predictions.append(cleaned)
        rows.append(
            {
                "sample_id": sample.sample_id,
                "ground_truth_date": sample.labels["date"],
                "legacy_date": legacy["date"],
                "cleaned_date": cleaned["date"],
                "date_changed": legacy["date"] != cleaned["date"],
            }
        )
    references = [sample.labels for sample in samples]
    legacy_metrics = evaluate_field_f1(legacy_predictions, references)
    cleaned_metrics = evaluate_field_f1(cleaned_predictions, references)
    legacy_by_field = {metric.field: metric for metric in legacy_metrics}
    cleaned_by_field = {metric.field: metric for metric in cleaned_metrics}
    legacy_date = legacy_by_field["date"]
    cleaned_date = cleaned_by_field["date"]
    corrected_macro = sum(metric.f1 for metric in cleaned_metrics) / len(cleaned_metrics)
    hybrid_macro = (
        sum(metric.f1 for metric in cleaned_metrics if metric.field != "date")
        + BASELINE_F1["date"]
    ) / 4
    recommendation = (
        "pure_layoutlmv3_date_path"
        if cleaned_date.f1 >= BASELINE_F1["date"]
        else "hybrid_offline_default"
    )
    return {
        "evaluation_type": "offline_checkpoint_inference",
        "evaluation_split": "local_validation_split_seed_42",
        "official_test": False,
        "integrated_into_api": False,
        "sample_count": len(samples),
        "legacy_field_metrics": [asdict(metric) for metric in legacy_metrics],
        "cleaned_field_metrics": [asdict(metric) for metric in cleaned_metrics],
        "legacy_date_metric": asdict(legacy_date),
        "cleaned_date_metric": asdict(cleaned_date),
        "date_f1_recovery": cleaned_date.f1 - legacy_date.f1,
        "corrected_layoutlmv3_macro_f1": corrected_macro,
        "hybrid_macro_f1": hybrid_macro,
        "recommendation": recommendation,
        "predictions": rows,
    }


def comparison_to_markdown(report: dict[str, object]) -> str:
    """生成旧/新日期重建 validation 对比报告。"""

    legacy = report["legacy_date_metric"]
    cleaned = report["cleaned_date_metric"]
    return "\n".join(
        [
            "# Date Reconstruction Checkpoint Inference",
            "",
            f"- evaluation_type: {report['evaluation_type']}",
            f"- evaluation_split: {report['evaluation_split']}",
            f"- official_test: {str(report['official_test']).lower()}",
            f"- integrated_into_api: {str(report['integrated_into_api']).lower()}",
            f"- sample_count: {report['sample_count']}",
            "",
            "| reconstruction | precision | recall | f1 |",
            "| --- | ---: | ---: | ---: |",
            f"| legacy | {legacy['precision']:.4f} | {legacy['recall']:.4f} | {legacy['f1']:.4f} |",
            f"| cleaned | {cleaned['precision']:.4f} | {cleaned['recall']:.4f} | {cleaned['f1']:.4f} |",
            "",
            f"- date_f1_recovery: {report['date_f1_recovery']:.4f}",
            f"- corrected_layoutlmv3_macro_f1: {report['corrected_layoutlmv3_macro_f1']:.4f}",
            f"- hybrid_macro_f1: {report['hybrid_macro_f1']:.4f}",
            f"- recommendation: {report['recommendation']}",
            "",
        ]
    )


def write_comparison_outputs(report: dict[str, object], output_dir: str | Path) -> dict[str, Path]:
    """保存 JSON、Markdown 和逐样本 JSONL。"""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "date_reconstruction_inference.json"
    markdown_path = output / "date_reconstruction_inference.md"
    predictions_path = output / "date_reconstruction_predictions.jsonl"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(comparison_to_markdown(report), encoding="utf-8")
    with predictions_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in report["predictions"]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {
        "json": json_path,
        "markdown": markdown_path,
        "predictions": predictions_path,
    }
