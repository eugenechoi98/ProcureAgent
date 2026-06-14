"""生成端到端案例证据包，不训练模型、不修改业务规则。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from procureguard.db.connection import initialize_database
from procureguard.db.json_utils import dumps_json
from procureguard.db.seed_policies import seed_policy_documents
from procureguard.extraction.datasets import read_processed_jsonl
from procureguard.extraction.field_reconstruction import reconstruct_bio_fields
from procureguard.extraction.layoutlmv3_dataset import create_layoutlmv3_processor
from procureguard.extraction.validation_inference import predict_sample_labels
from procureguard.models.invoice import ExtractedFields
from procureguard.phase3.explanation.facts import CanonicalAuditFacts
from procureguard.phase3.explanation.guard import LoRAOutputGuard
from procureguard.phase3.explanation.orchestrator import FallbackOrchestrator
from procureguard.phase3.explanation.renderer import DeterministicTemplateRenderer
from procureguard.phase3.explanation.rewrite_contract import RewriteResponse
from procureguard.phase3.schemas import AnomalySample
from procureguard.repositories.invoice_repository import InvoiceRepository
from procureguard.services.agent_processor import AgentInvoiceProcessor


OUTPUT_ROOT = PROJECT_ROOT / "demo" / "e2e_cases"
REPORT_ROOT = PROJECT_ROOT / "reports" / "demo"
VALIDATION_PATH = (
    PROJECT_ROOT / "data" / "phase1" / "sroie_task3" / "processed" / "validation.jsonl"
)
CASE_SPECS = {
    "case_a_standard_pass": {
        "sample_id": "68f28c61d47a8203ad797fd1",
        "title": "标准收据字段抽取与低风险审核",
        "po_number": "PO-E2E-A",
        "grn_number": "GRN-E2E-A",
        "invoice_number": "SROIE-E2E-A",
    },
    "case_b_date_layout_challenge": {
        "sample_id": "68f28c63d47a8203ad798055",
        "title": "日期版式挑战与日期重建",
        "po_number": "PO-E2E-B",
        "grn_number": "GRN-E2E-B",
        "invoice_number": "SROIE-E2E-B",
    },
}
FIELD_COLORS = {
    "COMPANY": "#d62728",
    "ADDRESS": "#1f77b4",
    "DATE": "#2ca02c",
    "TOTAL": "#9467bd",
}


def _write_json(path: Path, payload: Any) -> None:
    """使用稳定 UTF-8 JSON 写入证据。"""

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _evidence_hashes(case_dir: Path, names: list[str]) -> dict[str, str]:
    """记录证据文件哈希，避免后续图片和 JSON 被无声替换。"""

    return {name: _sha256(case_dir / name) for name in names}


def _sha256(path: Path) -> str:
    """计算证据文件哈希。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pixel_box(box: tuple[int, int, int, int], image: Image.Image) -> tuple[int, int, int, int]:
    """将 LayoutLMv3 的 0-1000 归一化 bbox 转回图片像素。"""

    width, height = image.size
    left, top, right, bottom = box
    return (
        round(left * width / 1000),
        round(top * height / 1000),
        round(right * width / 1000),
        round(bottom * height / 1000),
    )


def _draw_ocr_boxes(sample: Any, output_path: Path) -> None:
    """将已有数据集 OCR bbox 可视化。"""

    image = Image.open(sample.image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for index, token in enumerate(sample.tokens, start=1):
        box = _pixel_box(tuple(token.bbox), image)
        draw.rectangle(box, outline="#0072B2", width=2)
        draw.text((box[0], max(0, box[1] - 11)), str(index), fill="#0072B2", font=font)
    image.save(output_path, optimize=True)


def _draw_prediction_boxes(
    sample: Any,
    labels: list[str],
    output_path: Path,
) -> None:
    """把 checkpoint 的 word-level BIO 预测画回原图。"""

    image = Image.open(sample.image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for token, label in zip(sample.tokens, labels, strict=True):
        if label == "O":
            continue
        field = label.split("-", 1)[1]
        color = FIELD_COLORS[field]
        box = _pixel_box(tuple(token.bbox), image)
        draw.rectangle(box, outline=color, width=3)
        draw.text(
            (box[0], max(0, box[1] - 12)),
            field.lower(),
            fill=color,
            font=font,
        )
    image.save(output_path, optimize=True)


def _field_rows(sample: Any, labels: list[str]) -> list[dict[str, Any]]:
    """保存 bbox 级真实预测，便于验证图片与字段来自同一链路。"""

    return [
        {
            "text": token.text,
            "bbox": list(token.bbox),
            "ocr_confidence": token.confidence,
            "predicted_label": label,
        }
        for token, label in zip(sample.tokens, labels, strict=True)
    ]


def _run_phase2(
    case_dir: Path,
    case_id: str,
    spec: dict[str, str],
    prediction: dict[str, str],
    source_image: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """使用 mock 采购上下文调用现有 Phase 2 审核引擎。"""

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    seed_policy_documents(conn)
    total = float(prediction["total"])
    conn.execute(
        """
        INSERT INTO purchase_orders
        (po_number, vendor_name, total_amount, currency, line_items_json, created_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            spec["po_number"],
            prediction["company"],
            total,
            "MYR",
            "[]",
            prediction["date"],
            "open",
        ),
    )
    conn.execute(
        """
        INSERT INTO goods_receipts
        (grn_number, po_number, received_date, line_items_json, receiver)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            spec["grn_number"],
            spec["po_number"],
            prediction["date"],
            "[]",
            "e2e-evidence-fixture",
        ),
    )
    invoice_id = f"e2e-{case_id}"
    InvoiceRepository(conn).create_invoice(
        invoice_id,
        str(source_image),
        _sha256(source_image),
    )
    extracted = ExtractedFields(
        vendor_name=prediction["company"],
        invoice_number=spec["invoice_number"],
        invoice_date=prediction["date"],
        po_number=spec["po_number"],
        total_amount=total,
        currency="MYR",
        line_items=[],
        extraction_confidence=1.0,
        extraction_model="layoutlmv3_best_offline_checkpoint",
    )
    audit_input = {
        "runtime": "existing_phase2_agent_invoice_processor",
        "extracted_fields": extracted.model_dump(mode="json"),
        "field_provenance": {
            "vendor_name": "offline_real_layoutlmv3_checkpoint_prediction",
            "invoice_date": "offline_real_layoutlmv3_checkpoint_prediction",
            "total_amount": "offline_real_layoutlmv3_checkpoint_prediction",
            "invoice_number": "mock_procurement_linkage_not_extracted_from_image",
            "po_number": "mock_procurement_linkage_not_extracted_from_image",
            "currency": "mock_context_matching_source_dataset_locale",
            "line_items": "not_available_from_sroie_four_field_task",
        },
        "purchase_order_context": {
            "source": "mock",
            "po_number": spec["po_number"],
            "vendor_name": prediction["company"],
            "total_amount": total,
            "currency": "MYR",
        },
        "goods_receipt_context": {
            "source": "mock",
            "grn_number": spec["grn_number"],
            "po_number": spec["po_number"],
            "line_items": [],
        },
    }
    report = AgentInvoiceProcessor(conn).process_extracted_invoice(
        invoice_id,
        extracted,
    )
    result = report.model_dump(mode="json")
    _write_json(case_dir / "phase2_audit_input.json", audit_input)
    _write_json(case_dir / "phase2_audit_result.json", result)
    _write_json(case_dir / "final_audit_report.json", result)
    conn.close()
    return audit_input, result


def _generate_layout_case(
    case_id: str,
    spec: dict[str, str],
    sample: Any,
    labels: list[str],
) -> dict[str, Any]:
    """生成一个 SROIE 到 Phase 2 的完整离线证据包。"""

    case_dir = OUTPUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / "source_invoice.png"
    Image.open(sample.image_path).convert("RGB").save(source_path, optimize=True)
    _draw_ocr_boxes(sample, case_dir / "ocr_boxes.png")
    _draw_prediction_boxes(sample, labels, case_dir / "layoutlmv3_predictions.png")

    prediction = reconstruct_bio_fields(sample.tokens, labels)
    ocr_payload = {
        "source": "existing_sroie_task3_dataset_artifact",
        "sample_id": sample.sample_id,
        "tokens": [
            {
                "text": token.text,
                "bbox": list(token.bbox),
                "confidence": token.confidence,
            }
            for token in sample.tokens
        ],
    }
    extracted_payload = {
        "sample_id": sample.sample_id,
        "inference_type": "offline_real_checkpoint_inference",
        "checkpoint_source": "local_external_artifact_layoutlmv3_best",
        "ground_truth": sample.labels,
        "prediction": prediction,
        "word_predictions": _field_rows(sample, labels),
    }
    _write_json(case_dir / "ocr_output.json", ocr_payload)
    _write_json(case_dir / "extracted_fields.json", extracted_payload)
    if case_id == "case_b_date_layout_challenge":
        _write_json(
            case_dir / "date_reconstruction.json",
            {
                "sample_id": sample.sample_id,
                "ground_truth_date": sample.labels["date"],
                "legacy_date": ": 30-04-2018 19:50:14",
                "cleaned_date": prediction["date"],
                "source": "offline_real_checkpoint_word_predictions_plus_existing_reconstruction_logic",
                "claim_scope": "single_case_example_only",
            },
        )
    audit_input, audit_result = _run_phase2(
        case_dir,
        case_id,
        spec,
        prediction,
        source_path,
    )
    license_note = (
        "Source: Voxel51/scanned_receipts, derived from ICDAR 2019 SROIE; "
        "dataset card license CC BY 4.0. The selected image contains business "
        "contact/order data but no identified natural-person customer name."
    )
    manifest = {
        "case_id": case_id,
        "case_title": spec["title"],
        "source_type": "SROIE",
        "source_sample_id": sample.sample_id,
        "source_license_or_note": license_note,
        "image_is_public_safe": True,
        "privacy_note": (
            "Public dataset receipt with business address/phone or order data; "
            "review again before external publication."
        ),
        "ocr_result_type": "existing_artifact",
        "layoutlmv3_prediction_type": "real_checkpoint_inference",
        "phase2_result_type": "real_runtime_engine",
        "phase2_context_type": "mock_po_grn_context",
        "lora_result_type": "not_available",
        "guard_result_type": "not_available",
        "claims_allowed": [
            "The image, OCR boxes, and LayoutLMv3 word predictions share the same SROIE sample_id.",
            "LayoutLMv3 predictions were generated offline from the saved local checkpoint.",
            "The existing Phase 2 engine produced the committed audit result from the packaged input.",
            "PO and GRN are explicitly marked mock procurement context.",
        ],
        "claims_forbidden": [
            "This single case proves overall LayoutLMv3 F1.",
            "PO number, GRN number, or invoice number were extracted from the SROIE image.",
            "The Phase 2 audit uses a real enterprise PO/GRN system.",
            "This is official SROIE test performance.",
        ],
        "field_provenance": audit_input["field_provenance"],
        "result_summary": {
            "risk_level": audit_result["risk_level"],
            "recommended_action": audit_result["recommended_action"],
        },
        "evidence_file_sha256": _evidence_hashes(
            case_dir,
            [
                "source_invoice.png",
                "ocr_boxes.png",
                "layoutlmv3_predictions.png",
                "ocr_output.json",
                "extracted_fields.json",
                "phase2_audit_input.json",
                "phase2_audit_result.json",
                "final_audit_report.json",
            ]
            + (
                ["date_reconstruction.json"]
                if case_id == "case_b_date_layout_challenge"
                else []
            ),
        ),
    }
    _write_json(case_dir / "manifest.json", manifest)
    notes = [
        f"# {spec['title']}",
        "",
        "- 图片、OCR 和 LayoutLMv3 bbox 预测通过同一个 `sample_id` 关联。",
        "- LayoutLMv3 为本地 checkpoint 的 CPU 离线真实推理。",
        "- SROIE Task 3 只提供 company/address/date/total；采购单号和收货单号是明确标注的 mock 上下文。",
        "- Phase 2 结果由现有 AgentInvoiceProcessor 实时计算后固化。",
        "- 单案例只说明链路和具体输出，不代表数据集整体 F1。",
    ]
    (case_dir / "notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    return manifest


def _find_test_sample(sample_id: str) -> dict[str, Any]:
    """从固定 Phase 3 test JSONL 中读取目标 fixture。"""

    path = PROJECT_ROOT / "data" / "phase3" / "generated" / "test.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if payload["sample_id"] == sample_id:
            return payload
    raise LookupError(f"Phase 3 sample not found: {sample_id}")


def _find_review_case(sample_id: str) -> dict[str, Any]:
    """读取已提交 review 中的真实离线 LoRA 输出。"""

    path = PROJECT_ROOT / "reports" / "phase3" / "phase3e_lora_review.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    def walk(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            if value.get("sample_id") == sample_id and value.get("model_output"):
                return value
            for item in value.values():
                found = walk(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found:
                    return found
        return None

    found = walk(payload)
    if found is None:
        raise LookupError(f"LoRA review case not found: {sample_id}")
    return found


def _generate_guard_case() -> dict[str, Any]:
    """生成真实 LoRA 输出经当前 Guard 拦截的证据包。"""

    case_id = "case_c_lora_guard_fallback"
    case_dir = OUTPUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    sample_id = "phase3-missing_goods_receipt-024"
    sample_payload = _find_test_sample(sample_id)
    sample = AnomalySample.model_validate(sample_payload)
    review_case = _find_review_case(sample_id)
    raw_output = review_case["model_output"]
    facts = CanonicalAuditFacts.from_input_facts(
        sample.input_facts,
        invoice_id=sample_id,
    )
    guard_result = LoRAOutputGuard().verify(facts, raw_output)
    renderer = DeterministicTemplateRenderer()
    fallback = FallbackOrchestrator(renderer=renderer).explain(
        facts,
        mode="experimental",
        rewrite_provider=lambda _: RewriteResponse(
            raw_text=raw_output,
            model_version="qwen2.5-0.5b-first-lora-offline-review",
            adapter_version="phase3_first_lora_run",
        ),
    )
    audit_facts = facts.stable_payload()
    guard_payload = {
        "check_type": "real_guard_check",
        "passed": guard_result.passed,
        "decision": "ACCEPT" if guard_result.passed else "REJECT",
        "violations": guard_result.violations,
        "expected_key_violation": "unknown_identifier:GRN-20260149",
    }
    final_report = {
        "case_id": case_id,
        "phase2_facts_type": "existing_synthetic_evaluation_fixture",
        "canonical_facts": audit_facts,
        "lora_raw_output_source": "existing_review_artifact",
        "guard": guard_payload,
        "fallback_reason": fallback.audit_trail.fallback_reason,
        "final_explanation_source": "deterministic_template",
        "final_explanation": fallback.explanation,
        "facts_hash": fallback.audit_trail.facts_hash,
        "template_version": fallback.audit_trail.template_version,
        "prompt_version": fallback.audit_trail.prompt_version,
    }
    _write_json(case_dir / "audit_facts.json", audit_facts)
    (case_dir / "lora_raw_output.txt").write_text(raw_output + "\n", encoding="utf-8")
    _write_json(case_dir / "guard_result.json", guard_payload)
    (case_dir / "fallback_explanation.md").write_text(
        "# Fallback 结果\n\n"
        f"- Guard 结论：REJECT\n"
        f"- fallback_reason：`{fallback.audit_trail.fallback_reason}`\n\n"
        f"{fallback.explanation}\n",
        encoding="utf-8",
    )
    (case_dir / "final_explanation.md").write_text(
        "# 最终正式解释\n\n" + fallback.explanation + "\n",
        encoding="utf-8",
    )
    _write_json(case_dir / "final_audit_report.json", final_report)
    manifest = {
        "case_id": case_id,
        "case_title": "真实离线 LoRA 幻觉、Guard 拦截与模板回退",
        "source_type": "existing_fixture",
        "source_license_or_note": (
            "Input facts are a generated Phase 3 evaluation fixture; raw LoRA output "
            "is copied from the first real offline ModelScope evaluation review."
        ),
        "image_is_public_safe": False,
        "layoutlmv3_prediction_type": "not_available",
        "phase2_result_type": "fixture_only",
        "lora_result_type": "real_offline_model_output",
        "guard_result_type": "real_guard_check",
        "claims_allowed": [
            "The raw text is an existing first-run offline LoRA model output.",
            "The current Guard rejects unsupported GRN-20260149.",
            "The final explanation is the deterministic template fallback.",
        ],
        "claims_forbidden": [
            "The input facts represent a real enterprise invoice.",
            "LoRA determines the risk level or recommended action.",
            "The LoRA model ran online in the public Demo.",
            "This case includes LayoutLMv3 image inference.",
        ],
        "evidence_file_sha256": _evidence_hashes(
            case_dir,
            [
                "audit_facts.json",
                "lora_raw_output.txt",
                "guard_result.json",
                "fallback_explanation.md",
                "final_explanation.md",
                "final_audit_report.json",
            ],
        ),
    }
    _write_json(case_dir / "manifest.json", manifest)
    (case_dir / "notes.md").write_text(
        "# LoRA Guard / fallback 证据边界\n\n"
        "- 输入事实是固定 synthetic evaluation fixture，不是真实采购交易。\n"
        "- 原始文本来自第一轮真实离线 LoRA 评测 artifact。\n"
        "- Guard 使用当前生产代码离线执行，结论为 REJECT。\n"
        "- fallback 使用当前确定性模板；LoRA 不参与风险判断。\n",
        encoding="utf-8",
    )
    return manifest


def _build_report(manifests: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总资产审计和可公开 claim。"""

    return {
        "ready": True,
        "scope": "batch_h0_e2e_case_evidence",
        "generated_case_count": len(manifests),
        "real_public_images_found": True,
        "image_prediction_one_to_one": True,
        "bbox_visualization_generated": True,
        "phase2_runtime_audit_generated": True,
        "real_lora_guard_case_generated": True,
        "dataset": {
            "name": "Voxel51/scanned_receipts",
            "origin": "ICDAR 2019 SROIE",
            "license": "CC BY 4.0 per dataset card",
            "privacy_note": (
                "Selected images contain business contact/order data; no identified "
                "natural-person customer name was observed."
            ),
        },
        "local_assets": {
            "checkpoint": "D:/ProcureAgent_LocalArtifacts/Phase1/layoutlmv3_best",
            "checkpoint_included": False,
            "sroie_images_in_git": False,
            "generated_evidence_images_included": True,
            "lora_weights_included": False,
        },
        "cases": manifests,
        "hf_demo_candidates": [
            "case_a_standard_pass",
            "case_b_date_layout_challenge",
            "case_c_lora_guard_fallback",
        ],
        "blockers": [],
        "claims_allowed": [
            "A/B use offline real LayoutLMv3 checkpoint inference on traceable SROIE samples.",
            "A/B Phase 2 audit results come from the existing runtime engine with mock PO/GRN context.",
            "C uses a real offline LoRA review output and a real current-code Guard check.",
        ],
        "claims_forbidden": [
            "Single examples prove dataset-level F1.",
            "Mock PO/GRN identifiers were extracted from receipt images.",
            "The public Demo performs live LayoutLMv3 or LoRA inference.",
            "The evidence is official test-set performance.",
        ],
    }


def _write_report(report: dict[str, Any]) -> None:
    """写入 JSON 和面向审查的 Markdown 报告。"""

    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_json(REPORT_ROOT / "e2e_case_evidence_report.json", report)
    lines = [
        "# E2E Case Evidence Report",
        "",
        "## 审计结论",
        "",
        "- 找到真实可追溯图片：YES（SROIE validation 样本）。",
        "- 图片与 LayoutLMv3 prediction 一一对应：YES（同一 sample_id）。",
        "- OCR / prediction bbox 可视化：YES。",
        "- extracted fields 进入 Phase 2 实时审核：YES，但 PO/GRN 为明确标注的 mock 上下文。",
        "- LoRA Guard/fallback 真实案例：YES，原始输出来自首轮真实离线评测。",
        "",
        "## 可进入后续 Demo 的案例",
        "",
    ]
    for case in report["cases"]:
        lines.append(
            f"- `{case['case_id']}`：{case['case_title']}；"
            f"LayoutLMv3={case['layoutlmv3_prediction_type']}；"
            f"Phase2={case['phase2_result_type']}；"
            f"LoRA={case['lora_result_type']}。"
        )
    lines.extend(
        [
            "",
            "## 关键边界",
            "",
            "- A/B 的图片、OCR 和模型预测可以按 sample_id 追溯。",
            "- A/B 的采购单号和收货单号不是图片抽取字段，而是 Phase 2 mock 上下文。",
            "- C 的输入事实是 synthetic evaluation fixture，只有 LoRA 原始输出和 Guard 校验属于真实离线证据。",
            "- 单案例不能用于证明整体 F1；整体指标仍只属于 Model Lab。",
            "- 本轮未修改或上传 Hugging Face Space。",
            "",
            "## 许可证与隐私",
            "",
            "- 数据源：Voxel51/scanned_receipts，源自 ICDAR 2019 SROIE。",
            "- 数据卡许可证：CC BY 4.0；公开展示时必须保留归属。",
            "- 所选图片包含企业地址、电话或订单信息；未观察到自然人顾客姓名，发布前仍建议再次人工复核。",
        ]
    )
    (REPORT_ROOT / "e2e_case_evidence_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def generate(checkpoint: Path) -> dict[str, Any]:
    """执行两条 LayoutLMv3 链和一条 LoRA Guard 链。"""

    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True)
    samples = {
        sample.sample_id: sample for sample in read_processed_jsonl(VALIDATION_PATH)
    }
    try:
        import torch
        from transformers import LayoutLMv3ForTokenClassification
    except ImportError as exc:
        raise SystemExit('Install extraction dependencies with: pip install -e ".[extraction]"') from exc

    processor = create_layoutlmv3_processor(checkpoint, local_files_only=True)
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        checkpoint,
        local_files_only=True,
        use_safetensors=True,
    ).to("cpu")
    model.eval()
    manifests: list[dict[str, Any]] = []
    for case_id, spec in CASE_SPECS.items():
        sample = samples[spec["sample_id"]]
        labels = predict_sample_labels(
            sample,
            processor=processor,
            model=model,
            torch_module=torch,
            device=torch.device("cpu"),
        )
        manifests.append(_generate_layout_case(case_id, spec, sample, labels))
    manifests.append(_generate_guard_case())
    report = _build_report(manifests)
    _write_report(report)
    return report


def main() -> int:
    """解析 checkpoint 路径并打印生成摘要。"""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            r"D:\ProcureAgent_LocalArtifacts\Phase1\layoutlmv3_best"
        ),
    )
    args = parser.parse_args()
    report = generate(args.checkpoint)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
