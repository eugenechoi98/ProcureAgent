"""三单匹配确定性规则。"""

from typing import Any

from procureguard.models.invoice import ExtractedFields, MismatchItem, ValidationResult


class ThreeWayMatcher:
    """发票、采购订单和收货记录的确定性匹配器。"""

    AMOUNT_TOLERANCE = 0.01

    def match(
        self,
        invoice: ExtractedFields,
        po: dict[str, Any] | None,
        grn: dict[str, Any] | None,
    ) -> ValidationResult:
        """执行金额、PO、GRN 数量匹配。"""

        mismatches: list[MismatchItem] = []
        po_match = bool(po and invoice.po_number == po.get("po_number"))
        amount_match = self._match_amount(invoice, po, mismatches)
        grn_match = self._match_grn(invoice, grn, mismatches)

        if not po_match:
            mismatches.append(
                MismatchItem(
                    field="po_number",
                    invoice_value=invoice.po_number,
                    expected_value=po.get("po_number") if po else None,
                )
            )

        return ValidationResult(
            po_match=po_match,
            grn_match=grn_match,
            amount_match=amount_match,
            duplicate_check=True,
            mismatches=mismatches,
        )

    def _match_amount(
        self,
        invoice: ExtractedFields,
        po: dict[str, Any] | None,
        mismatches: list[MismatchItem],
    ) -> bool:
        """检查发票总额是否在 PO 金额 1% 误差内。"""

        if not po or invoice.total_amount is None:
            return False

        expected = float(po["total_amount"])
        diff = abs(invoice.total_amount - expected)
        amount_match = diff <= expected * self.AMOUNT_TOLERANCE
        if not amount_match:
            mismatches.append(
                MismatchItem(
                    field="total_amount",
                    invoice_value=invoice.total_amount,
                    expected_value=expected,
                    diff=diff,
                )
            )
        return amount_match

    def _match_grn(
        self,
        invoice: ExtractedFields,
        grn: dict[str, Any] | None,
        mismatches: list[MismatchItem],
    ) -> bool:
        """检查发票数量是否超过已收货数量。"""

        if not grn:
            return False

        grn_items = {
            item["item"]: item.get("received_qty", 0)
            for item in grn.get("line_items", [])
        }
        grn_match = True
        for item in invoice.line_items:
            received_qty = grn_items.get(item.item)
            if received_qty is None or item.qty > received_qty:
                grn_match = False
                mismatches.append(
                    MismatchItem(
                        field="quantity",
                        item=item.item,
                        invoice_value=item.qty,
                        received_value=received_qty,
                    )
                )
        return grn_match
