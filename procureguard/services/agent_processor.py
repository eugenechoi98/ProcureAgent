"""Agent 工具调用主链，串联三单匹配、政策检索和风险计算。"""

import sqlite3
import time
from typing import Any

from procureguard.models.audit import AuditReport, EvidenceItem
from procureguard.models.invoice import ExtractedFields, GoodsReceipt, MismatchItem
from procureguard.models.status import InvoiceStatus, RecommendedAction
from procureguard.repositories import AuditTraceRepository, InvoiceRepository
from procureguard.services.policy_rag import PolicyRAG
from procureguard.services.risk_engine import RiskAssessment, RiskEngine
from procureguard.services.validator import ThreeWayMatcher
from procureguard.tools import (
    check_duplicate_invoice,
    lookup_goods_receipt,
    lookup_purchase_order,
    retrieve_policy,
    submit_manual_review,
)


class AgentInvoiceProcessor:
    """执行真实规则闭环，但不负责 OCR 或 API 路由接入。"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.invoices = InvoiceRepository(conn)
        self.traces = AuditTraceRepository(conn)
        self.matcher = ThreeWayMatcher()
        self.risk_engine = RiskEngine()

    def process_extracted_invoice(
        self,
        invoice_id: str,
        extracted_fields: ExtractedFields,
    ) -> AuditReport:
        """基于已抽取字段执行 Agent 审核主链。"""

        started_at = time.perf_counter()
        self.invoices.update_status(invoice_id, InvoiceStatus.PROCESSING)
        self.invoices.update_extracted_fields(invoice_id, extracted_fields.model_dump(mode="json"))
        self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="extraction",
            input_data={"source": "provided_extracted_fields"},
            output_data=extracted_fields.model_dump(mode="json"),
            latency_ms=0,
        )

        tool_calls: list[dict[str, Any]] = []
        po_result = self._call_tool(
            tool_calls,
            "lookup_purchase_order",
            {"po_number": extracted_fields.po_number or ""},
            lambda: lookup_purchase_order(self.conn, extracted_fields.po_number or ""),
        )
        grn_result = self._call_tool(
            tool_calls,
            "lookup_goods_receipt",
            {"po_number": extracted_fields.po_number or ""},
            lambda: lookup_goods_receipt(self.conn, extracted_fields.po_number or ""),
        )
        duplicate_result = self._call_tool(
            tool_calls,
            "check_duplicate_invoice",
            {
                "invoice_number": extracted_fields.invoice_number or "",
                "vendor_name": extracted_fields.vendor_name or "",
                "current_invoice_id": invoice_id,
            },
            lambda: check_duplicate_invoice(
                self.conn,
                invoice_number=extracted_fields.invoice_number or "",
                vendor_name=extracted_fields.vendor_name or "",
                current_invoice_id=invoice_id,
            ),
        )

        validation = self.matcher.match(
            invoice=extracted_fields,
            po=po_result.purchase_order.model_dump(mode="json") if po_result.purchase_order else None,
            grn=self._merge_receipts(grn_result.receipts),
        )
        validation.duplicate_check = duplicate_result.duplicate_check
        if duplicate_result.is_duplicate:
            validation.mismatches.append(
                MismatchItem(
                    field="invoice_number",
                    invoice_value=extracted_fields.invoice_number,
                    expected_value="unique invoice number per vendor",
                )
            )

        self.invoices.update_validation_result(invoice_id, validation.model_dump(mode="json"))
        self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="validation",
            input_data={
                "invoice": extracted_fields.model_dump(mode="json"),
                "purchase_order_found": po_result.found,
                "goods_receipt_found": grn_result.found,
                "duplicate_check": duplicate_result.model_dump(mode="json"),
            },
            output_data=validation.model_dump(mode="json"),
        )

        policy_flags = PolicyRAG(self.conn).check_policy_violation(extracted_fields, validation)
        policy_results = self._call_tool(
            tool_calls,
            "retrieve_policy",
            {"query": self._policy_query(policy_flags), "top_k": 3},
            lambda: retrieve_policy(self.conn, query=self._policy_query(policy_flags), top_k=3),
        )
        assessment = self.risk_engine.assess(extracted_fields, validation, policy_flags)
        evidence = self._build_evidence(validation, duplicate_result.matched_invoice_ids)

        review_submission = None
        if assessment.recommended_action == RecommendedAction.REQUEST_HUMAN_APPROVAL:
            review_submission = self._call_tool(
                tool_calls,
                "submit_manual_review",
                {
                    "invoice_id": invoice_id,
                    "risk_level": assessment.risk_level.value,
                    "reason_codes": assessment.reason_codes,
                    "evidence": [item.model_dump(mode="json") for item in evidence],
                },
                lambda: submit_manual_review(
                    self.conn,
                    invoice_id=invoice_id,
                    risk_level=assessment.risk_level,
                    reason_codes=assessment.reason_codes,
                    evidence=[item.model_dump(mode="json") for item in evidence],
                ),
            )
        elif assessment.recommended_action == RecommendedAction.REJECT:
            self.invoices.update_status(
                invoice_id,
                InvoiceStatus.REJECTED,
                risk_level=assessment.risk_level.value,
            )
        else:
            self.invoices.update_status(
                invoice_id,
                InvoiceStatus.APPROVED,
                risk_level=assessment.risk_level.value,
            )

        agent_trace = self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="agent_call",
            input_data={
                "invoice_id": invoice_id,
                "policy_flags": policy_flags,
                "policy_result_count": len(policy_results),
            },
            output_data={
                "recommended_action": assessment.recommended_action.value,
                "review_id": review_submission.review_id if review_submission else None,
            },
            tool_calls=tool_calls,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
        )
        report = self._build_report(
            invoice_id=invoice_id,
            invoice=extracted_fields,
            validation=validation,
            policy_flags=policy_flags,
            assessment=assessment,
            evidence=evidence,
            trace_id=agent_trace["id"],
        )
        self.invoices.update_audit_report(invoice_id, report.model_dump(mode="json"))
        self.traces.create_trace(
            invoice_id=invoice_id,
            step_name="risk_calc",
            input_data={
                "validation": validation.model_dump(mode="json"),
                "policy_flags": policy_flags,
            },
            output_data={
                "assessment": self._assessment_to_dict(assessment),
                "audit_report": report.model_dump(mode="json"),
            },
        )
        return report

    def _call_tool(
        self,
        tool_calls: list[dict[str, Any]],
        name: str,
        arguments: dict[str, Any],
        callback,
    ):
        """执行工具并记录 function calling 形态的输入输出。"""

        started_at = time.perf_counter()
        result = callback()
        output = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in result
        ] if isinstance(result, list) else result.model_dump(mode="json")
        tool_calls.append(
            {
                "name": name,
                "arguments": arguments,
                "output": output,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            }
        )
        return result

    def _merge_receipts(self, receipts: list[GoodsReceipt]) -> dict[str, Any] | None:
        """把同一个 PO 的多张收货单合并成三单匹配输入。"""

        if not receipts:
            return None
        received_by_item: dict[str, float] = {}
        for receipt in receipts:
            for item in receipt.line_items:
                received_by_item[item["item"]] = (
                    received_by_item.get(item["item"], 0) + item.get("received_qty", 0)
                )
        return {
            "grn_number": ",".join(receipt.grn_number for receipt in receipts),
            "po_number": receipts[0].po_number,
            "received_date": receipts[-1].received_date,
            "line_items": [
                {"item": item, "received_qty": qty}
                for item, qty in received_by_item.items()
            ],
            "receiver": receipts[-1].receiver,
        }

    def _policy_query(self, policy_flags: list[str]) -> str:
        """把原因码转换成 FTS 更容易命中的英文关键词。"""

        if not policy_flags:
            return "invoice approval three way match"
        query_parts = {
            "high_value_approval_required": "approval threshold",
            "missing_or_invalid_po": "purchase order",
            "goods_receipt_mismatch": "goods receipt quantity",
            "amount_discrepancy": "amount tolerance",
            "duplicate_invoice": "duplicate invoice",
            "manual_review_required": "manual review",
        }
        terms: list[str] = []
        for flag in policy_flags:
            terms.extend(query_parts.get(flag, flag.replace("_", " ")).split())
        return " OR ".join(dict.fromkeys(terms))

    def _build_evidence(
        self,
        validation,
        duplicate_invoice_ids: list[str],
    ) -> list[EvidenceItem]:
        """把校验差异转换成审计报告证据。"""

        evidence = [
            EvidenceItem(
                field=item.field,
                invoice_value=item.invoice_value,
                received_value=item.received_value,
                expected_value=item.expected_value,
            )
            for item in validation.mismatches
        ]
        if duplicate_invoice_ids:
            evidence.append(
                EvidenceItem(
                    field="matched_invoice_ids",
                    invoice_value=duplicate_invoice_ids,
                    expected_value=[],
                )
            )
        return evidence

    def _build_report(
        self,
        invoice_id: str,
        invoice: ExtractedFields,
        validation,
        policy_flags: list[str],
        assessment: RiskAssessment,
        evidence: list[EvidenceItem],
        trace_id: str,
    ) -> AuditReport:
        """生成最终 AuditReport。"""

        return AuditReport(
            invoice_id=invoice_id,
            vendor=invoice.vendor_name or "Unknown vendor",
            total_amount=invoice.total_amount or 0.0,
            currency=invoice.currency,
            po_match=validation.po_match,
            goods_receipt_match=validation.grn_match,
            policy_flags=policy_flags,
            risk_level=assessment.risk_level,
            recommended_action=assessment.recommended_action,
            evidence=evidence,
            anomaly_explanation=assessment.anomaly_explanation,
            trace_id=trace_id,
        )

    def _assessment_to_dict(self, assessment: RiskAssessment) -> dict[str, Any]:
        """转换风险结果，便于写入 trace JSON。"""

        return {
            "risk_level": assessment.risk_level.value,
            "recommended_action": assessment.recommended_action.value,
            "reason_codes": assessment.reason_codes,
            "anomaly_explanation": assessment.anomaly_explanation,
        }
