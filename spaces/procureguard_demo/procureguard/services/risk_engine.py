"""根据规则校验结果计算发票风险。"""

from dataclasses import dataclass, field

from procureguard.models.invoice import ExtractedFields, ValidationResult
from procureguard.models.status import RecommendedAction, RiskLevel


@dataclass(frozen=True)
class RiskAssessment:
    """风险计算结果。"""

    risk_level: RiskLevel
    recommended_action: RecommendedAction
    reason_codes: list[str] = field(default_factory=list)
    anomaly_explanation: str = "No anomaly found."


class RiskEngine:
    """把确定性规则结果转换成风险等级和建议动作。"""

    def assess(
        self,
        invoice: ExtractedFields,
        validation: ValidationResult,
        policy_flags: list[str],
    ) -> RiskAssessment:
        """计算最终风险，不依赖 LLM 做金额或状态判断。"""

        reason_codes = list(dict.fromkeys(policy_flags + self._validation_reasons(validation)))
        if not validation.duplicate_check:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                recommended_action=RecommendedAction.REJECT,
                reason_codes=reason_codes,
                anomaly_explanation="Duplicate invoice detected for the same vendor and invoice number.",
            )

        hard_failures = [
            "missing_or_invalid_po",
            "goods_receipt_mismatch",
            "amount_discrepancy",
        ]
        if any(reason in reason_codes for reason in hard_failures):
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                recommended_action=RecommendedAction.REQUEST_HUMAN_APPROVAL,
                reason_codes=reason_codes,
                anomaly_explanation="Invoice requires human review because matching rules found discrepancies.",
            )

        if "high_value_approval_required" in reason_codes:
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                recommended_action=RecommendedAction.REQUEST_HUMAN_APPROVAL,
                reason_codes=reason_codes,
                anomaly_explanation="Invoice amount exceeds the manager approval threshold.",
            )

        return RiskAssessment(
            risk_level=RiskLevel.LOW,
            recommended_action=RecommendedAction.AUTO_APPROVE,
            reason_codes=reason_codes,
            anomaly_explanation="Invoice matched PO, goods receipt, amount, duplicate, and policy checks.",
        )

    def _validation_reasons(self, validation: ValidationResult) -> list[str]:
        """从校验布尔值补齐稳定的原因码。"""

        reasons: list[str] = []
        if not validation.po_match:
            reasons.append("missing_or_invalid_po")
        if not validation.grn_match:
            reasons.append("goods_receipt_mismatch")
        if not validation.amount_match:
            reasons.append("amount_discrepancy")
        if not validation.duplicate_check:
            reasons.append("duplicate_invoice")
        return reasons
