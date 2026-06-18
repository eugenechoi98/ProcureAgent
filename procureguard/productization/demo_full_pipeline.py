"""演示全链路 API 编排：真实 LayoutLMv3 抽取 + mock PO/GRN 查询 + Phase 2 审核。"""

from __future__ import annotations

from dataclasses import dataclass
import gc
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from procureguard.extraction.live_spike import (
    DEFAULT_CHECKPOINT,
    LiveExtractionFailure,
    check_live_extraction_assets,
    run_live_extraction,
)
from procureguard.models.audit import AuditReport
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.phase3.explanation.orchestrator import RewriteProvider
from procureguard.productization.demo_seed import resolve_demo_procurement_context
from procureguard.productization.e2e_audit import _mismatches_from_evidence, _run_phase2
from procureguard.productization.manual_audit import ExplicitMockProcurementContext


CONTEXT_SOURCE = "full_pipeline_demo_mock_db"


class DemoFullPipelineError(RuntimeError):
    """全链路 demo 的稳定错误，禁止伪造 OCR fallback。"""

    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


class DemoAuditPayload(BaseModel):
    """响应中的审计摘要。"""

    risk_level: str
    recommended_action: str
    raw: dict[str, Any]


class DemoFullPipelineResponse(BaseModel):
    """POST /api/demo/full_pipeline 的严格响应结构。"""

    demo_mode: Literal[True] = True
    context_source: Literal["full_pipeline_demo_mock_db"] = CONTEXT_SOURCE
    live_layoutlmv3_used: Literal[True] = True
    field_candidates: dict[str, Any]
    procurement_context: dict[str, Any]
    audit: DemoAuditPayload
    explanation: str


@dataclass(frozen=True)
class LayoutLMv3ExtractionResult:
    """真实 LayoutLMv3 运行后的字段候选与可审计字段。"""

    field_candidates: dict[str, Any]
    extracted_fields: ExtractedFields
    trace: dict[str, Any]


def run_demo_full_pipeline(
    *,
    image_bytes: bytes,
    filename: str | None,
    database_path: str | Path,
    explanation_rewrite_provider: RewriteProvider | None = None,
) -> DemoFullPipelineResponse:
    """执行上传图片到 AuditReport 的一步式 demo 链路。"""

    extraction = run_layoutlmv3(image_bytes=image_bytes, filename=filename)
    _release_model_memory()
    context, context_payload = DemoPOGRNStore(database_path).resolve(extraction.extracted_fields)
    audit_fields = _fields_for_audit(extraction.extracted_fields, context)
    report = _run_phase2(
        f"demo_full_{uuid4().hex}",
        audit_fields,
        context,
        explanation_mode="guarded_lora",
        explanation_rewrite_provider=explanation_rewrite_provider,
    )
    raw = _report_payload(report)
    raw["source_labels"] = {
        "demo_mode": True,
        "context_source": CONTEXT_SOURCE,
        "payment_authority": False,
        "live_layoutlmv3_used": True,
        "risk_decision_source": "deterministic_rules",
    }
    if context is None:
        raw["context_resolution"] = {
            "status": "no_po_found",
            "risk_hint": "medium",
        }
    raw["field_extraction_trace"] = extraction.trace
    return DemoFullPipelineResponse(
        field_candidates=extraction.field_candidates,
        procurement_context=context_payload,
        audit=DemoAuditPayload(
            risk_level=report.risk_level.value,
            recommended_action=report.recommended_action.value,
            raw=raw,
        ),
        explanation=_explanation_text(report),
    )


def run_layoutlmv3(*, image_bytes: bytes, filename: str | None = None) -> LayoutLMv3ExtractionResult:
    """把上传图片写入临时目录并调用真实 LayoutLMv3 live extraction。"""

    if not image_bytes:
        raise DemoFullPipelineError("empty_upload", "Uploaded invoice image is empty.")
    work_dir = Path(".tmp") / "demo_full_pipeline" / uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    image_path = work_dir / "invoice.jpg"
    _write_normalized_image(image_bytes, image_path)
    output_dir = work_dir / "layoutlmv3"
    try:
        checkpoint = _select_layoutlmv3_checkpoint(image_path)
        live_result = run_live_extraction(image_path, output_dir, checkpoint=checkpoint)
        candidate_payload = _read_json(output_dir / "layoutlmv3_field_candidates.json")
        ocr_payload = _read_json(output_dir / "ocr_tokens.json")
    except LiveExtractionFailure as exc:
        raise DemoFullPipelineError(
            "layoutlmv3_failed",
            exc.message,
            {"failure_code": exc.code, "remediation": exc.remediation},
        ) from exc
    except Exception as exc:
        raise DemoFullPipelineError(
            "layoutlmv3_failed",
            f"LayoutLMv3 live extraction failed: {exc}",
        ) from exc

    field_candidates = _normalize_candidates(candidate_payload, ocr_payload)
    extracted = _candidates_to_extracted_fields(field_candidates)
    return LayoutLMv3ExtractionResult(
        field_candidates=field_candidates,
        extracted_fields=extracted,
        trace={
            "output_dir": str(output_dir),
            "latency_seconds": live_result.get("latency_seconds"),
            "token_count": ocr_payload.get("token_count"),
            "source": "live_layoutlmv3",
        },
    )


class DemoPOGRNStore:
    """只读 demo PO/GRN 查询层，按发票号优先、供应商关键词兜底。"""

    def __init__(self, database_path: str | Path):
        self.database_path = database_path

    def resolve(
        self,
        fields: ExtractedFields,
    ) -> tuple[ExplicitMockProcurementContext | None, dict[str, Any]]:
        """返回 Phase 2 可用 context 和 API 展示 payload。"""

        context, source = resolve_demo_procurement_context(self.database_path, fields)
        if context is None:
            return None, {
                "status": "no_po_found",
                "risk_hint": "medium",
                "lookup_priority": ["invoice_number_exact", "vendor_name_keyword"],
                "source": CONTEXT_SOURCE,
            }
        return context, {
            "status": "found",
            "source": CONTEXT_SOURCE,
            "lookup_source": source,
            "po_number": context.po_number,
            "po_vendor_name": context.po_vendor_name,
            "po_total_amount": context.po_total_amount,
            "po_currency": context.po_currency,
            "grn_number": context.grn_number,
            "grn_available": context.grn_available,
            "duplicate_invoice_exists": context.duplicate_invoice_exists,
        }


def _normalize_candidates(candidate_payload: dict[str, Any], ocr_payload: dict[str, Any]) -> dict[str, Any]:
    """将 SROIE 字段候选映射成 demo API 需要的字段名。"""

    by_name = {
        str(item.get("field_name", "")).lower(): item
        for item in candidate_payload.get("fields", [])
        if isinstance(item, dict)
    }
    tokens = _token_texts(ocr_payload)
    invoice_number = _candidate_value(by_name, "invoice_number") or _extract_invoice_number(tokens)
    vendor_name = (
        _candidate_value(by_name, "vendor_name")
        or _candidate_value(by_name, "company")
        or _extract_vendor_from_tokens(tokens)
    )
    total_text = (
        _candidate_value(by_name, "total_amount")
        or _candidate_value(by_name, "total")
        or _extract_total_from_tokens(tokens)
    )
    total_amount = _parse_amount(total_text)
    invoice_date = _candidate_value(by_name, "invoice_date") or _candidate_value(by_name, "date")
    confidence_values = [
        item.get("confidence")
        for item in by_name.values()
        if isinstance(item.get("confidence"), int | float)
    ]
    confidence = (
        sum(float(value) for value in confidence_values) / len(confidence_values)
        if confidence_values
        else 0.0
    )
    return {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "total_amount": total_amount,
        "invoice_date": invoice_date,
        "currency": "MYR",
        "line_items": [
            {
                "item": "Receipt total",
                "qty": 1,
                "unit_price": total_amount or 0,
                "amount": total_amount or 0,
            }
        ],
        "raw_layoutlmv3_fields": candidate_payload.get("fields", []),
        "ocr_token_count": ocr_payload.get("token_count", len(tokens)),
        "extraction_confidence": round(confidence, 4),
        "requires_human_confirmation": True,
        "source": "live_layoutlmv3",
    }


def _candidates_to_extracted_fields(field_candidates: dict[str, Any]) -> ExtractedFields:
    """将真实候选字段转换为 Phase 2 可接收的 ExtractedFields。"""

    return ExtractedFields(
        vendor_name=field_candidates.get("vendor_name") or "unknown",
        invoice_number=field_candidates.get("invoice_number") or "unknown",
        invoice_date=field_candidates.get("invoice_date"),
        total_amount=float(field_candidates.get("total_amount") or 0),
        currency=str(field_candidates.get("currency") or "MYR"),
        line_items=[
            LineItem(
                item=str(item.get("item") or "Receipt total"),
                qty=float(item.get("qty") or 1),
                unit_price=float(item["unit_price"]) if item.get("unit_price") is not None else None,
                amount=float(item["amount"]) if item.get("amount") is not None else None,
            )
            for item in field_candidates.get("line_items", [])
        ],
        extraction_confidence=float(field_candidates.get("extraction_confidence") or 0),
        extraction_model="live_layoutlmv3_full_pipeline",
    )


def _fields_for_audit(
    fields: ExtractedFields,
    context: ExplicitMockProcurementContext | None,
) -> ExtractedFields:
    """补齐 PO 和行项目，Phase 2 仍只做确定性规则判断。"""

    if context is None:
        return fields.model_copy(
            update={
                "po_number": fields.po_number or "NO-PO-FOUND",
                "line_items": fields.line_items or _fallback_line_items(fields),
            }
        )
    return fields.model_copy(
        update={
            "po_number": context.po_number,
            "currency": context.po_currency,
            "line_items": fields.line_items or _fallback_line_items(fields),
        }
    )


def _fallback_line_items(fields: ExtractedFields) -> list[LineItem]:
    return [
        LineItem(
            item="Receipt total",
            qty=1,
            unit_price=fields.total_amount or 0,
            amount=fields.total_amount or 0,
        )
    ]


def _report_payload(report: AuditReport) -> dict[str, Any]:
    payload = report.model_dump(mode="json")
    payload["mismatches"] = _mismatches_from_evidence(payload.get("evidence", []))
    return payload


def _explanation_text(report: AuditReport) -> str:
    if report.explanation:
        return report.explanation.explanation_text
    return report.anomaly_explanation


def _write_normalized_image(image_bytes: bytes, output: Path) -> None:
    """把上传图片解码成 RGB JPEG，避免 OCR 底层受编码差异影响。"""

    try:
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as loaded:
            image = loaded.convert("RGB")
            max_side = 1200
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side))
            image.save(output, format="JPEG", quality=95)
    except Exception as exc:
        raise DemoFullPipelineError(
            "image_decode_failed",
            f"Uploaded invoice image cannot be decoded: {exc}",
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_layoutlmv3_checkpoint(sample_image: Path) -> Path:
    """选择已验证真实 LayoutLMv3 runtime bundle，不允许 mock 或 base model 替代。"""

    candidates = [
        Path(path)
        for path in os.getenv("PROCUREGUARD_LAYOUTLMV3_CHECKPOINT_DIRS", "").split(os.pathsep)
        if path.strip()
    ]
    candidates.extend(
        [
            Path(DEFAULT_CHECKPOINT),
            Path("artifacts/phase1_runtime/layoutlmv3_sroie_corrected"),
        ]
    )
    failures: list[dict[str, Any]] = []
    for candidate in candidates:
        assets = check_live_extraction_assets(candidate, sample_image=sample_image)
        if assets["status"]:
            return candidate
        failures.append(
            {
                "checkpoint": str(candidate),
                "failure_codes": assets["failure_codes"],
            }
        )
    raise DemoFullPipelineError(
        "layoutlmv3_failed",
        "No valid fine-tuned LayoutLMv3 runtime bundle was found.",
        {"checked_bundles": failures},
    )


def _candidate_value(by_name: dict[str, dict[str, Any]], name: str) -> Any | None:
    item = by_name.get(name)
    if not item:
        return None
    value = item.get("predicted_value")
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _token_texts(ocr_payload: dict[str, Any]) -> list[str]:
    texts = []
    for token in ocr_payload.get("tokens", []):
        if isinstance(token, dict) and token.get("text"):
            texts.append(str(token["text"]))
    return texts


def _extract_invoice_number(tokens: list[str]) -> str | None:
    joined = " ".join(tokens)
    patterns = [
        r"\bPEGIV[-\s]?\d+\b",
        r"\bCS\d{6,}\b",
        r"\bINV[-\s]?[A-Z0-9-]*\d[A-Z0-9-]*\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, joined, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper().replace(" ", "-")
    return None


def _extract_vendor_from_tokens(tokens: list[str]) -> str | None:
    joined = " ".join(tokens).upper()
    known_vendors = [
        "OJC MARKETING SDN BHD",
        "PERNIAGAAN ZHENG HUI",
        "ZHENG HUI",
    ]
    for vendor in known_vendors:
        if vendor in joined:
            return vendor
    return None


def _extract_total_from_tokens(tokens: list[str]) -> str | None:
    joined = " ".join(tokens)
    total_match = re.search(r"TOTAL\s*[:：]?\s*(?:RM|MYR)?\s*([0-9]+(?:[.,][0-9]{2})?)", joined, re.IGNORECASE)
    if total_match:
        return total_match.group(1)
    amounts = re.findall(r"\b[0-9]+(?:[.,][0-9]{2})\b", joined)
    return amounts[-1] if amounts else None


def _parse_amount(value: Any | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"[0-9]+(?:[,.][0-9]{2})?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def clear_demo_full_pipeline_tmp() -> None:
    """测试辅助：清理 full pipeline 临时目录。"""

    shutil.rmtree(Path(".tmp") / "demo_full_pipeline", ignore_errors=True)


def _release_model_memory() -> None:
    """在 OCR/LayoutLMv3 后释放内存，再进入可选 LoRA provider。"""

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        return
