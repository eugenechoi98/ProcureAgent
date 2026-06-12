"""本地 Demo 服务层，隔离 Gradio UI 与审核业务逻辑。"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from procureguard.db import initialize_database, seed_mock_data, seed_policy_documents
from procureguard.db.connection import get_connection
from procureguard.models.invoice import ExtractedFields, LineItem
from procureguard.phase3.explanation import (
    CanonicalAuditFacts,
    RewriteRequest,
    RewriteResponse,
    generate_guarded_explanation,
)
from procureguard.repositories import InvoiceRepository
from procureguard.services import AgentInvoiceProcessor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "phase3h_demo_cases.json"
)

ExplanationSelection = Literal[
    "template",
    "shadow",
    "experimental_guard_pass",
    "experimental_guard_fail",
    "provider_runtime_error",
    "invalid_output",
]

EXPLANATION_MODES: tuple[ExplanationSelection, ...] = (
    "template",
    "shadow",
    "experimental_guard_pass",
    "experimental_guard_fail",
    "provider_runtime_error",
    "invalid_output",
)


class DemoOutput(BaseModel):
    """页面展示所需的稳定输出结构。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    invoice_id: str
    execution_path: Literal["hybrid", "static_fallback"]
    static_fallback: bool
    static_fallback_reason: str | None = None
    risk_level: str
    recommended_action: str
    anomaly_types: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    explanation_text: str
    explanation_source: str
    explanation_mode: str
    used_rewrite: bool
    guard_passed: bool
    fallback_reason: str | None = None
    facts_hash: str
    template_version: str
    prompt_version: str
    model_version: str
    adapter_version: str
    raw_rewrite_output: str | None = None
    audit_report: dict[str, Any]
    safe_error_summary: str | None = None


class HybridCaseUnavailable(RuntimeError):
    """当前 Phase 2 无法精确复现 fixture 时触发静态 fallback。"""


class DemoService:
    """运行实时混合链，并在失败时提供明确的静态样例 fallback。"""

    def __init__(
        self,
        fixture_path: Path = DEFAULT_FIXTURE_PATH,
        hybrid_runner: Callable[[dict[str, Any], ExplanationSelection], DemoOutput]
        | None = None,
    ) -> None:
        self.fixture_path = fixture_path
        self._cases = self._load_cases(fixture_path)
        self._hybrid_runner = hybrid_runner or self._run_hybrid_case

    @property
    def case_ids(self) -> list[str]:
        """返回 fixture 顺序稳定的 case id。"""

        return list(self._cases)

    @property
    def explanation_modes(self) -> list[str]:
        """返回页面可选解释模式。"""

        return list(EXPLANATION_MODES)

    def run_case(
        self,
        case_id: str,
        explanation_mode: ExplanationSelection = "template",
    ) -> DemoOutput:
        """优先运行混合链，任何不支持或运行失败都进入静态 fallback。"""

        case = self._get_case(case_id)
        if explanation_mode not in EXPLANATION_MODES:
            raise ValueError(f"Unsupported explanation mode: {explanation_mode}")
        try:
            return self._hybrid_runner(case, explanation_mode)
        except Exception as exc:
            return self._run_static_fallback(case, explanation_mode, exc)

    def _run_hybrid_case(
        self,
        case: dict[str, Any],
        explanation_mode: ExplanationSelection,
    ) -> DemoOutput:
        """运行固定 ExtractedFields 到实时 Phase 2 和解释层的混合链。"""

        if case["case_id"] != "normal_invoice":
            raise HybridCaseUnavailable(
                "当前 Phase 2 fixture 不能精确复现该场景，使用静态样例。"
            )

        facts = case["facts"]
        conn = get_connection(":memory:")
        try:
            initialize_database(conn)
            seed_mock_data(conn)
            seed_policy_documents(conn)
            InvoiceRepository(conn).create_invoice(
                invoice_id=facts["invoice_id"],
                file_path=f"demo/{case['case_id']}.pdf",
                file_hash=f"demo-hash-{case['case_id']}",
            )
            mode, provider = self._resolve_explanation_mode(explanation_mode)
            report = AgentInvoiceProcessor(
                conn,
                explanation_mode=mode,
                explanation_rewrite_provider=provider,
            ).process_extracted_invoice(
                facts["invoice_id"],
                ExtractedFields(
                    vendor_name=facts["vendor_name"],
                    invoice_number=facts["invoice_number"],
                    invoice_date="2026-06-10",
                    po_number=facts["po_number"],
                    total_amount=facts["total_amount"],
                    currency=facts["currency"],
                    line_items=[
                        LineItem(item="Printer Paper", qty=100),
                        LineItem(item="Toner Cartridge", qty=4),
                    ],
                    extraction_confidence=1.0,
                    extraction_model="demo-pre-generated-fields-v1",
                ),
            )
            explanation = report.explanation
            if explanation is None:
                raise RuntimeError("AuditReport did not contain explanation metadata.")
            return DemoOutput(
                case_id=case["case_id"],
                invoice_id=report.invoice_id,
                execution_path="hybrid",
                static_fallback=False,
                risk_level=report.risk_level.value,
                recommended_action=report.recommended_action.value,
                anomaly_types=explanation.anomaly_types,
                evidence=explanation.evidence,
                missing_fields=explanation.missing_fields,
                explanation_text=explanation.explanation_text,
                explanation_source=explanation.explanation_source,
                explanation_mode=explanation.explanation_mode,
                used_rewrite=explanation.used_rewrite,
                guard_passed=explanation.guard_passed,
                fallback_reason=explanation.fallback_reason,
                facts_hash=explanation.facts_hash,
                template_version=explanation.template_version,
                prompt_version=explanation.prompt_version,
                model_version=explanation.model_version,
                adapter_version=explanation.adapter_version,
                raw_rewrite_output=explanation.raw_llm_output,
                audit_report=report.model_dump(mode="json"),
            )
        finally:
            conn.close()

    def _run_static_fallback(
        self,
        case: dict[str, Any],
        explanation_mode: ExplanationSelection,
        error: Exception,
    ) -> DemoOutput:
        """使用已验收 Canonical Facts，并明确标记不是实时审核成功。"""

        facts = CanonicalAuditFacts.model_validate(case["facts"])
        mode, provider = self._resolve_explanation_mode(explanation_mode)
        result, metadata = generate_guarded_explanation(
            facts,
            mode=mode,
            rewrite_provider=provider,
        )
        safe_error = f"{error.__class__.__name__}: {error}"
        audit_report = {
            "invoice_id": facts.invoice_id,
            "vendor": facts.vendor_name,
            "total_amount": facts.total_amount,
            "currency": facts.currency,
            "risk_level": facts.risk_level,
            "recommended_action": facts.recommended_action,
            "evidence": metadata.evidence,
            "anomaly_explanation": metadata.explanation_text,
            "explanation": metadata.model_dump(mode="json"),
            "demo_metadata": {
                "execution_path": "static_fallback",
                "fallback_reason": "hybrid_execution_unavailable",
                "safe_error_summary": safe_error,
            },
        }
        return DemoOutput(
            case_id=case["case_id"],
            invoice_id=facts.invoice_id or case["case_id"],
            execution_path="static_fallback",
            static_fallback=True,
            static_fallback_reason="hybrid_execution_unavailable",
            risk_level=facts.risk_level,
            recommended_action=facts.recommended_action,
            anomaly_types=[item.value for item in facts.anomaly_types],
            evidence=metadata.evidence,
            missing_fields=list(facts.missing_fields),
            explanation_text=result.explanation,
            explanation_source=metadata.explanation_source,
            explanation_mode=metadata.explanation_mode,
            used_rewrite=metadata.used_rewrite,
            guard_passed=metadata.guard_passed,
            fallback_reason=metadata.fallback_reason,
            facts_hash=metadata.facts_hash,
            template_version=metadata.template_version,
            prompt_version=metadata.prompt_version,
            model_version=metadata.model_version,
            adapter_version=metadata.adapter_version,
            raw_rewrite_output=metadata.raw_llm_output,
            audit_report=audit_report,
            safe_error_summary=safe_error,
        )

    def _resolve_explanation_mode(
        self, selection: ExplanationSelection
    ) -> tuple[str, Callable[[RewriteRequest], Any] | None]:
        """把页面选项转换为 orchestrator mode 和 fake provider。"""

        if selection == "template":
            return "template", None
        if selection == "shadow":
            return "shadow", self._passing_provider
        if selection == "experimental_guard_pass":
            return "experimental", self._passing_provider
        if selection == "experimental_guard_fail":
            return "experimental", self._unsafe_provider
        if selection == "provider_runtime_error":
            return "experimental", self._runtime_error_provider
        return "experimental", self._invalid_provider

    def _passing_provider(self, request: RewriteRequest) -> RewriteResponse:
        """返回 guard 可通过的 fake rewrite。"""

        return RewriteResponse(
            raw_text=request.template_output,
            model_version="fake-demo-model",
            adapter_version="fake-demo-adapter",
        )

    def _unsafe_provider(self, request: RewriteRequest) -> RewriteResponse:
        """注入未知发票号，验证 guard fail-closed。"""

        target = request.facts.invoice_number or "未提供（缺失）"
        return RewriteResponse(
            raw_text=request.template_output.replace(
                target, "INV-UNSUPPORTED-999"
            ),
            model_version="fake-demo-model",
            adapter_version="fake-demo-adapter",
        )

    def _runtime_error_provider(self, _request: RewriteRequest) -> None:
        """模拟 provider 运行失败。"""

        raise RuntimeError("fake demo provider runtime error")

    def _invalid_provider(self, _request: RewriteRequest) -> int:
        """模拟非法 provider 输出。"""

        return 123

    def _get_case(self, case_id: str) -> dict[str, Any]:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise ValueError(f"Unknown demo case: {case_id}") from exc

    def _load_cases(self, path: Path) -> dict[str, dict[str, Any]]:
        """只读加载已验收 fixture，并阻止重复 case id。"""

        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = {case["case_id"]: case for case in payload}
        if len(cases) != len(payload):
            raise ValueError("Demo fixture contains duplicate case ids.")
        return cases
