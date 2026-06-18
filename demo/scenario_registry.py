"""HF Demo 场景注册表：Path B 的唯一数据源。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parent

FIELD_LABELS = {
    "invoice_number": "发票编号",
    "po_number": "PO编号",
    "grn_number": "GRN编号",
    "total_amount": "总金额",
    "vendor_name": "供应商",
    "date": "日期",
    "item_list": "项目",
}

FIELD_CONFIDENCES = {
    "invoice_number": 0.98,
    "po_number": 0.95,
    "grn_number": 0.93,
    "total_amount": 0.97,
    "vendor_name": 0.91,
    "date": 0.89,
    "item_list": 0.85,
}

PRE_AUDIT_FORBIDDEN_FLAGS = {
    "mismatch",
    "warning",
    "duplicate",
    "high risk",
    "不一致",
    "高风险",
    "重复",
    "缺失",
}


@dataclass(frozen=True)
class CrossDocumentContext:
    """跨文档对比场景的数据源。"""

    invoice_total: float
    po_total: float
    grn_total: float
    vendor_invoice: str
    vendor_po: str
    vendor_grn: str


@dataclass(frozen=True)
class Scenario:
    """单个发票图片绑定的完整演示数据。"""

    case_id: str
    scenario_id: str
    scenario_type: str
    image_path: str
    display_name: str
    summary: str
    risk_level: str
    recommended_action: str
    audit_result: str
    audit_reason: str
    fields: dict[str, str]
    cross_document: CrossDocumentContext | None = None


SCENARIO_REGISTRY: dict[str, Scenario] = {
    "normal_invoice": Scenario(
        case_id="normal_invoice",
        scenario_id="scenario_001",
        scenario_type="single_document",
        image_path="assets/cases/scenario_001.png",
        display_name="案例 1：正常标准发票",
        summary="字段、PO、GRN 和金额均来自 scenario_001，用于展示标准场景流程。",
        risk_level="low",
        recommended_action="auto_approve",
        audit_result="pass",
        audit_reason="PO、GRN 与金额均一致，系统判定可通过。",
        fields={
            "invoice_number": "INV-2505-1001",
            "po_number": "PO-2505-7789",
            "grn_number": "GRN-2505-3344",
            "total_amount": "USD 2,614.22",
            "vendor_name": "Northbridge Supplies Ltd",
            "date": "2025-05-15",
            "item_list": "Office supplies bundle",
        },
    ),
    "missing_goods_receipt": Scenario(
        case_id="missing_goods_receipt",
        scenario_id="scenario_002",
        scenario_type="single_document",
        image_path="assets/cases/scenario_002.png",
        display_name="案例 2：日期版式非标准",
        summary="图片、字段、PO、GRN 和金额均绑定 scenario_002，用于展示版式变化下的一致流程。",
        risk_level="low",
        recommended_action="auto_approve",
        audit_result="pass",
        audit_reason="PO、GRN 与金额均一致，系统判定可通过。",
        fields={
            "invoice_number": "INV-2505-2002",
            "po_number": "PO-2505-8890",
            "grn_number": "GRN-2505-8890",
            "total_amount": "USD 3,600.00",
            "vendor_name": "Summit Office Trading",
            "date": "2025-05-31",
            "item_list": "Warehouse receiving batch",
        },
    ),
    "missing_po_number": Scenario(
        case_id="missing_po_number",
        scenario_id="scenario_003",
        scenario_type="single_document",
        image_path="assets/cases/scenario_003.png",
        display_name="案例 3：PO/GRN 版式变化",
        summary="图片、字段、PO、GRN 和金额均绑定 scenario_003，用于展示字段位置变化但数据同源。",
        risk_level="low",
        recommended_action="auto_approve",
        audit_result="pass",
        audit_reason="PO、GRN 与金额均一致，系统判定可通过。",
        fields={
            "invoice_number": "INV-2505-3003",
            "po_number": "PO-2505-3303",
            "grn_number": "GRN-2505-3303",
            "total_amount": "USD 2,400.00",
            "vendor_name": "Blue Harbor Services",
            "date": "2025-05-20",
            "item_list": "Facility service charge",
        },
    ),
    "vendor_name_mismatch": Scenario(
        case_id="vendor_name_mismatch",
        scenario_id="scenario_004",
        scenario_type="cross_document",
        image_path="assets/cases/scenario_004.png",
        display_name="案例 4：金额对账案例",
        summary="图片、供应商、PO、GRN 和金额均绑定 scenario_004，用于展示跨文档金额核验。",
        risk_level="high",
        recommended_action="reject",
        audit_result="not_pass",
        audit_reason="发票金额、采购单金额与收货金额不一致，系统拒绝通过。",
        fields={
            "invoice_number": "INV-2505-4004",
            "po_number": "PO-2505-4404",
            "grn_number": "GRN-2505-4404",
            "total_amount": "USD 4,100.00",
            "vendor_name": "Adventure Works Services",
            "date": "2025-05-22",
            "item_list": "IT service package",
        },
        cross_document=CrossDocumentContext(
            invoice_total=4100.00,
            po_total=3900.00,
            grn_total=4000.00,
            vendor_invoice="Adventure Works Services",
            vendor_po="Adventure Works Services",
            vendor_grn="Adventure Works Services",
        ),
    ),
    "duplicate_invoice": Scenario(
        case_id="duplicate_invoice",
        scenario_id="scenario_005",
        scenario_type="cross_document",
        image_path="assets/cases/scenario_005.png",
        display_name="案例 5：供应商核对案例",
        summary="图片、字段、PO、GRN 和金额均绑定 scenario_005，用于展示跨文档供应商核验。",
        risk_level="high",
        recommended_action="reject",
        audit_result="not_pass",
        audit_reason="发票供应商、采购单供应商与收货供应商存在冲突，系统拒绝通过。",
        fields={
            "invoice_number": "INV-2505-5005",
            "po_number": "PO-2505-7789",
            "grn_number": "GRN-2505-3344",
            "total_amount": "USD 2,614.22",
            "vendor_name": "Northbridge Supplies Ltd",
            "date": "2025-05-15",
            "item_list": "Office supplies bundle",
        },
        cross_document=CrossDocumentContext(
            invoice_total=2614.22,
            po_total=2614.22,
            grn_total=2614.22,
            vendor_invoice="Northbridge Supplies Ltd",
            vendor_po="ProcureGuard Office Supply Co",
            vendor_grn="Summit Receiving Services",
        ),
    ),
}


def get_scenario(case_id: str) -> Scenario:
    """按 case_id 读取唯一 scenario。"""

    try:
        scenario = SCENARIO_REGISTRY[case_id]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario case_id: {case_id}") from exc
    validate_scenario(scenario)
    return scenario


def scenario_image_path(scenario: Scenario) -> str:
    """返回 scenario 绑定图片的绝对路径。"""

    return str((DEMO_ROOT / scenario.image_path).resolve())


def scenario_field_rows(scenario: Scenario) -> list[list[Any]]:
    """把 scenario 字段映射为 UI 字段表。"""

    return [
        [FIELD_LABELS[field], value, FIELD_CONFIDENCES[field], "已识别", False]
        for field, value in scenario.fields.items()
    ]


def scenario_rule_rows(scenario: Scenario) -> list[list[str]]:
    """Run Audit 后从 scenario 数据生成规则审计结果。"""

    if scenario.scenario_type == "single_document":
        return [
            ["发票字段完整", scenario.fields["invoice_number"], "TRUE"],
            ["发票金额可读", scenario.fields["total_amount"], "TRUE"],
            ["单文档场景", "不执行 PO/GRN mismatch 判断", "TRUE"],
        ]
    context = scenario.cross_document
    if context is None:
        raise ValueError(f"Cross-document scenario missing context: {scenario.scenario_id}")
    amount_match = (
        context.invoice_total == context.po_total == context.grn_total
    )
    vendor_match = (
        context.vendor_invoice == context.vendor_po == context.vendor_grn
    )
    return [
        [
            "金额跨文档一致",
            (
                f"Invoice USD {context.invoice_total:,.2f} / "
                f"PO USD {context.po_total:,.2f} / "
                f"GRN USD {context.grn_total:,.2f}"
            ),
            "TRUE" if amount_match else "FALSE",
        ],
        [
            "供应商跨文档一致",
            (
                f"Invoice {context.vendor_invoice} / "
                f"PO {context.vendor_po} / "
                f"GRN {context.vendor_grn}"
            ),
            "TRUE" if vendor_match else "FALSE",
        ],
    ]


def scenario_evidence_rows(scenario: Scenario) -> list[list[str]]:
    """返回同源场景证据说明。"""

    return [
        ["scenario_id", scenario.scenario_id, "图片、字段、审计和解释的唯一绑定键"],
        ["数据来源", "scenario_registry", "未调用 OCR、LayoutLMv3 或随机生成"],
    ]


def scenario_choices() -> list[tuple[str, str]]:
    """返回 Path B 下拉选项，标签只来自 registry。"""

    return [(scenario.display_name, case_id) for case_id, scenario in SCENARIO_REGISTRY.items()]


def scenario_mapping_payload(execution_id: str, scenario: Scenario) -> dict[str, Any]:
    """生成 debug 用 scenario mapping。"""

    return {
        "execution_id": execution_id,
        "scenario_id": scenario.scenario_id,
        "case_id": scenario.case_id,
        "image_path": scenario.image_path,
        "state": "已展示OCR",
        "source": "scenario_registry",
        "realtime_ocr": False,
        "scenario_type": scenario.scenario_type,
        "cross_document": (
            {
                "invoice_total": scenario.cross_document.invoice_total,
                "po_total": scenario.cross_document.po_total,
                "grn_total": scenario.cross_document.grn_total,
                "vendor_invoice": scenario.cross_document.vendor_invoice,
                "vendor_po": scenario.cross_document.vendor_po,
                "vendor_grn": scenario.cross_document.vendor_grn,
            }
            if scenario.cross_document
            else None
        ),
        "fields": [
            {
                "field": field,
                "label": FIELD_LABELS[field],
                "value": value,
                "confidence": FIELD_CONFIDENCES[field],
                "status": "已识别",
                "requires_human_confirmation": False,
            }
            for field, value in scenario.fields.items()
        ],
    }


def scenario_explanation(scenario: Scenario, lora_mode: str) -> str:
    """返回 LoRA OFF/ON 固定解释。"""

    risk = {"low": "低风险", "medium": "中风险", "high": "高风险"}[
        scenario.risk_level
    ]
    if lora_mode == "LoRA ON":
        return (
            f"系统完成 {scenario.scenario_id} 的多维度规则核验，"
            f"{scenario.audit_reason} 因此该发票被评估为{risk}状态。"
        )
    return (
        f"基于 {scenario.scenario_id} 的确定性规则审计，"
        f"{scenario.audit_reason} 风险等级为{risk}。"
    )


def validate_scenario(scenario: Scenario) -> None:
    """渲染前校验图片、OCR、审计同源。"""

    required = {
        "invoice_number",
        "po_number",
        "grn_number",
        "total_amount",
        "vendor_name",
        "date",
        "item_list",
    }
    if set(scenario.fields) != required:
        raise ValueError(f"Scenario fields mismatch: {scenario.scenario_id}")
    if not scenario.scenario_id or not scenario.image_path:
        raise ValueError("Scenario missing id or image path.")
    if scenario.scenario_type not in {"single_document", "cross_document"}:
        raise ValueError(f"Invalid scenario type: {scenario.scenario_type}")
    if scenario.scenario_type == "single_document" and scenario.cross_document:
        raise ValueError(f"Single-document scenario has cross context: {scenario.scenario_id}")
    if scenario.scenario_type == "cross_document" and scenario.cross_document is None:
        raise ValueError(f"Cross-document scenario missing context: {scenario.scenario_id}")
    if not (DEMO_ROOT / scenario.image_path).is_file():
        raise FileNotFoundError(f"Scenario image missing: {scenario.image_path}")
    for key, value in scenario.fields.items():
        if value in ("", None) or str(value).startswith("NO_"):
            raise ValueError(
                f"Invalid scenario field {scenario.scenario_id}.{key}: {value!r}"
            )


def assert_no_pre_audit_flags(scenario: Scenario) -> None:
    """Run Audit 前禁止展示 mismatch/warning/risk 旗标。"""

    image_name = Path(scenario.image_path).name.lower()
    text = f"{scenario.display_name} {scenario.summary} {image_name}".lower()
    hits = [flag for flag in PRE_AUDIT_FORBIDDEN_FLAGS if flag in text]
    if hits:
        raise ValueError(
            f"Pre-audit display contains forbidden flags for {scenario.scenario_id}: {hits}"
        )


def assert_same_scenario(*scenario_ids: str) -> None:
    """强制 image / OCR / audit / explanation 使用同一 scenario_id。"""

    unique = set(scenario_ids)
    if len(unique) != 1:
        raise ValueError(f"Scenario mismatch before render: {sorted(unique)}")
