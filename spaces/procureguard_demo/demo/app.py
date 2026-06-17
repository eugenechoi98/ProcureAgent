"""构建和启动本地离线 Gradio Demo。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from typing import Any

from demo.architecture_view import ARCHITECTURE_MARKDOWN
from demo.demo_service import DemoOutput, DemoService
from demo.invoice_case_view import (
    case_choices,
    load_invoice_case_catalog,
    preview_values,
    render_completed_status,
    render_explanation,
    render_pending_status,
    render_risk_action,
)
from demo.scenario_registry import (
    SCENARIO_REGISTRY,
    assert_no_pre_audit_flags,
    assert_same_scenario,
    get_scenario,
    scenario_choices,
    scenario_evidence_rows,
    scenario_explanation,
    scenario_field_rows,
    scenario_image_path,
    scenario_mapping_payload,
    scenario_rule_rows,
)
from procureguard.productization.manual_audit import (
    ManualAuditRequest,
    run_manual_audit,
)

DEMO_ROOT = Path(__file__).resolve().parent
MAIN_CHAIN_ROOT = DEMO_ROOT / "e2e_cases" / "case_a_standard_pass"

try:
    import gradio as gr
except ModuleNotFoundError as exc:
    if exc.name != "gradio":
        raise
    gr = None

_GRADIO_INSTALL_MESSAGE = (
    '本地 Demo 需要 Gradio，请先运行：'
    '.\\.venv\\Scripts\\python.exe -m pip install -e ".[demo]"'
)


def _require_gradio() -> Any:
    """缺少 Demo 专用依赖时给出明确安装提示。"""

    if gr is None:
        raise RuntimeError(_GRADIO_INSTALL_MESSAGE)
    return gr


def _summary_markdown(result: DemoOutput) -> str:
    """生成紧凑状态摘要，并明确标记静态 fallback。"""

    path_label = (
        "静态回退结果" if result.static_fallback else "实时混合审核"
    )
    fallback = result.static_fallback_reason or "无"
    return (
        f"### {path_label}\n"
        f"**案例：** `{result.case_id}`  \n"
        f"**发票：** `{result.invoice_id}`  \n"
        f"**风险等级：** `{result.risk_level}`  \n"
        f"**建议动作：** `{result.recommended_action}`  \n"
        f"**演示回退原因：** `{fallback}`"
    )


def _run_for_ui(
    service: DemoService,
    catalog: dict[str, dict[str, Any]],
    case_id: str,
    explanation_mode: str,
) -> tuple[Any, ...]:
    """把 service 输出转换为 Gradio 组件值。"""

    result = service.run_case(case_id, explanation_mode)
    case = catalog[case_id]
    return (
        case["match_rows"],
        case["evidence_rows"],
        render_completed_status(case, result),
        render_risk_action(case, result),
        render_explanation(case, result),
        _summary_markdown(result),
        result.case_id,
        result.invoice_id,
        result.risk_level,
        result.recommended_action,
        result.anomaly_types,
        result.evidence,
        result.missing_fields,
        result.explanation_text,
        result.explanation_source,
        result.used_rewrite,
        result.guard_passed,
        result.fallback_reason or "",
        result.facts_hash,
        result.template_version,
        result.prompt_version,
        result.model_version,
        result.adapter_version,
        result.raw_rewrite_output or "",
        result.safe_error_summary or "",
        result.audit_report,
    )


def _preview_for_ui(
    catalog: dict[str, dict[str, Any]], case_id: str
) -> tuple[Any, ...]:
    """补充操作区状态，同时保持案例预览和内部模式值同步。"""

    preview = preview_values(catalog, case_id)
    return (*preview[:-1], render_pending_status(catalog[case_id]), preview[-1])


def _run_manual_audit_for_ui(
    vendor_name: str,
    invoice_number: str,
    invoice_date: str,
    total_amount: float,
    currency: str,
    po_number: str,
    grn_number: str,
    duplicate_invoice_exists: bool,
) -> tuple[str, str, str, dict[str, Any]]:
    """Path A：把手动字段送入现有确定性审核链。"""

    payload = {
        "invoice_fields": {
            "invoice_number": invoice_number,
            "vendor_name": vendor_name,
            "invoice_date": invoice_date,
            "total_amount": total_amount,
            "currency": currency,
            "po_number": po_number,
            "line_items": [
                {
                    "item": "Receipt total",
                    "quantity": 1,
                    "unit_price": total_amount,
                    "amount": total_amount,
                }
            ],
        },
        "procurement_context": {
            "po_number": po_number,
            "po_vendor_name": vendor_name,
            "po_total_amount": total_amount,
            "po_currency": currency,
            "po_status": "open",
            "po_line_items": [
                {
                    "item": "Receipt total",
                    "quantity": 1,
                    "unit_price": total_amount,
                    "amount": total_amount,
                }
            ],
            "grn_available": bool(grn_number.strip()),
            "grn_number": grn_number.strip() or None,
            "grn_received_date": invoice_date if grn_number.strip() else None,
            "grn_line_items": [
                {"item": "Receipt total", "received_quantity": 1}
            ]
            if grn_number.strip()
            else [],
            "duplicate_invoice_exists": duplicate_invoice_exists,
            "policy_profile": "mock_default",
        },
        "metadata": {
            "source": "manual_input",
            "context_source": "explicit_mock_context",
            "explanation_mode": "template",
            "user_note": "HF UI Path A manual audit.",
        },
    }
    response = run_manual_audit(ManualAuditRequest.model_validate(payload))
    report = response.audit_report.model_dump(mode="json")
    summary = (
        "### Path A Result\n"
        f"**Risk level:** `{response.risk_level}`  \n"
        f"**Recommended action:** `{response.recommended_action}`  \n"
        "**Decision source:** `deterministic_rules`  \n"
        "**ML used:** `false`  \n"
        "**Payment authority:** `false`"
    )
    explanation = (
        "### Explanation\n"
        f"{response.audit_report.explanation.explanation_text if response.audit_report.explanation else response.audit_report.anomaly_explanation}\n\n"
        "LoRA is not used in Path A. The result is generated by the deterministic audit engine."
    )
    return response.risk_level, response.recommended_action, summary + "\n\n" + explanation, report


def _risk_zh(value: str) -> str:
    """把风险值转成面试展示友好的中文。"""

    return {"low": "低风险", "medium": "中风险", "high": "高风险"}.get(value, value)


def _action_zh(value: str) -> str:
    """把建议动作转成面试展示友好的中文。"""

    return {
        "auto_approve": "自动通过",
        "request_human_approval": "转人工复核",
        "reject": "拒绝",
    }.get(value, value)


def _read_main_chain() -> dict[str, Any]:
    """读取主链路展示所需的已验收离线证据。"""

    return {
        "ocr": json.loads((MAIN_CHAIN_ROOT / "ocr_output.json").read_text(encoding="utf-8")),
        "fields": json.loads((MAIN_CHAIN_ROOT / "extracted_fields.json").read_text(encoding="utf-8")),
        "audit": json.loads((MAIN_CHAIN_ROOT / "phase2_audit_result.json").read_text(encoding="utf-8")),
        "image": str((MAIN_CHAIN_ROOT / "source_invoice.png").resolve()),
        "ocr_boxes": str((MAIN_CHAIN_ROOT / "ocr_boxes.png").resolve()),
        "predictions": str((MAIN_CHAIN_ROOT / "layoutlmv3_predictions.png").resolve()),
    }


def _main_chain_initial_values() -> tuple[Any, ...]:
    """第一页初始值：先展示图片、OCR、字段和人工确认结果，结果待运行。"""

    data = _read_main_chain()
    prediction = data["fields"]["prediction"]
    tokens = data["ocr"]["tokens"][:8]
    ocr_rows = [[item["text"], item["confidence"]] for item in tokens]
    field_rows = [
        ["供应商", prediction["company"], "已确认"],
        ["发票日期", prediction["date"], "已确认"],
        ["总金额", prediction["total"], "已确认"],
        ["PO 编号", "PO-E2E-A", "人工补充演示上下文"],
        ["GRN 编号", "GRN-E2E-A", "人工补充演示上下文"],
    ]
    pending_card = (
        "### 运行审核后显示结果\n\n"
        "点击按钮后，这里会优先显示风险等级、建议动作和最终审核解释。"
    )
    return (
        data["image"],
        ocr_rows,
        field_rows,
        pending_card,
        "待运行",
        "待运行",
        "待运行",
        {},
    )


def _run_main_chain_for_ui() -> tuple[str, str, str, str, dict[str, Any]]:
    """第一页运行按钮：展示已验收主链路的 Phase 2 审核结果。"""

    audit = _read_main_chain()["audit"]
    explanation = audit["explanation"]["explanation_text"]
    risk = audit["risk_level"]
    action = audit["recommended_action"]
    result_card = (
        "## 审核结果\n\n"
        f"### 风险等级：{_risk_zh(risk)}\n"
        f"### 建议动作：{_action_zh(action)}\n\n"
        "### 最终审核解释\n"
        f"{explanation}\n\n"
        "**说明：** 发票字段来自图片识别；采购单与收货单为演示用上下文；"
        "三单匹配用于展示规则审核逻辑。"
    )
    return _risk_zh(risk), _action_zh(action), explanation, result_card, audit


def _case_validation_values(
    service: DemoService, catalog: dict[str, dict[str, Any]], case_id: str
) -> tuple[str, str, str, str, str]:
    """第二页五案例：只展示案例、核心问题、结果和判断原因。"""

    case = catalog[case_id]
    result = service.run_case(case_id, case["recommended_mode"])
    why = "；".join(row[1] for row in case["evidence_rows"])
    summary = (
        f"## {case['display_name']}\n\n"
        f"**核心问题：** {case['summary']}\n\n"
        f"**风险等级：** {_risk_zh(result.risk_level)}  \n"
        f"**建议动作：** {_action_zh(result.recommended_action)}\n\n"
        f"**为什么这样判断：** {why}。"
    )
    return (
        summary,
        case["summary"],
        _risk_zh(result.risk_level),
        _action_zh(result.recommended_action),
        why,
    )


def _explanation_view_to_mode(
    catalog: dict[str, dict[str, Any]], case_id: str, view: str
) -> str:
    """把结果区解释切换转换为 DemoService 的受控模式。"""

    if view == "Template":
        return "template"
    if view == "LoRA":
        return "experimental_guard_pass"
    return catalog[case_id]["recommended_mode"]


def _result_card_markdown(
    case: dict[str, Any], result: DemoOutput, explanation_view: str
) -> str:
    """渲染审核结果首屏卡片。"""

    return (
        "## Audit Result\n\n"
        f"### 风险等级：{_risk_zh(result.risk_level)}\n"
        f"### 建议动作：{_action_zh(result.recommended_action)}\n\n"
        f"**当前案例：** {case['display_name']}  \n"
        f"**解释视图：** {explanation_view}  \n"
        f"**解释来源：** `{result.explanation_source}`  \n"
        f"**Guard 通过：** `{str(result.guard_passed).lower()}`  \n"
        f"**fallback：** `{result.fallback_reason or '无'}`\n\n"
        "LoRA 只改变解释文本，不改变风险等级或建议动作。"
    )


def _case_trace(result: DemoOutput, explanation_view: str) -> dict[str, Any]:
    """生成结果区 trace，突出模型与规则边界。"""

    return {
        "explanation_view": explanation_view,
        "risk_level": result.risk_level,
        "recommended_action": result.recommended_action,
        "risk_action_source": "deterministic_rules",
        "lora_affects_decision": False,
        "explanation_source": result.explanation_source,
        "used_rewrite": result.used_rewrite,
        "guard_passed": result.guard_passed,
        "fallback_reason": result.fallback_reason,
        "raw_rewrite_output": result.raw_rewrite_output,
        "execution_path": result.execution_path,
        "static_fallback": result.static_fallback,
    }


def _path_b_preview(
    catalog: dict[str, dict[str, Any]], case_id: str
) -> tuple[Any, ...]:
    """Path B：运行前只展示当前图片，不预填 OCR、审计或解释结果。"""

    scenario = get_scenario(case_id)
    case = catalog[case_id]
    assert_no_pre_audit_flags(scenario)
    return (
        (
            "### 当前案例\n"
            f"**{scenario.display_name}**  \n"
            f"{scenario.summary}  \n"
            f"**scenario_id：** `{scenario.scenario_id}`"
        ),
        (
            "#### 1. 发票示意图\n"
            f"图片绑定 `{scenario.scenario_id}`；字段、审计和解释均从 registry 读取。"
        ),
        scenario_image_path(scenario),
        [],
        {},
        [],
        [],
        "### 未运行\n\n点击 Run Audit 后才会创建新的 execution_id 并执行 OCR。",
        "### 未运行\n\n尚未生成解释。",
        render_pending_status(case),
        "",
        "",
        {},
        {},
    )


def _scenario_result_card(execution_id: str, scenario: Any, lora_mode: str) -> str:
    """生成预置审计结果卡片。"""

    passed = scenario.audit_result == "pass"
    rule_rows = scenario_rule_rows(scenario)
    rule_text = "\n".join(
        f"- {name}：`{status}`（{value}）" for name, value, status in rule_rows
    )
    return (
        "## Audit Result\n\n"
        f"**execution_id：** `{execution_id}`  \n"
        "**状态：** 已完成审计  \n"
        f"**风险等级：** {_risk_zh(scenario.risk_level)}  \n"
        f"**审计结果：** {'通过' if passed else '不通过'}  \n"
        f"**建议动作：** {_action_zh(scenario.recommended_action)}\n\n"
        "### 规则命中说明\n"
        f"{rule_text}\n\n"
        f"### LoRA {lora_mode}\n"
        f"{scenario_explanation(scenario, lora_mode)}"
    )

def _run_path_b_scenario_for_ui(
    catalog: dict[str, dict[str, Any]],
    case_id: str,
    lora_mode: str,
) -> tuple[Any, ...]:
    """Run Audit：绑定预置 scenario 并按流程展示固定结果。"""

    execution_id = f"exec_{uuid4().hex}"
    case = catalog[case_id]
    scenario = get_scenario(case_id)
    assert_no_pre_audit_flags(scenario)
    image_scenario_id = scenario.scenario_id
    ocr_scenario_id = scenario.scenario_id
    audit_scenario_id = scenario.scenario_id
    explanation_scenario_id = scenario.scenario_id
    assert_same_scenario(
        image_scenario_id,
        ocr_scenario_id,
        audit_scenario_id,
        explanation_scenario_id,
    )
    status = (
        "### 已完成审计\n"
        f"**execution_id：** `{execution_id}`  \n"
        "**状态机：** `已加载 → 已展示OCR → 已完成审计`  \n"
        f"**当前案例：** {scenario.display_name}  \n"
        f"**scenario_id：** `{scenario.scenario_id}`  \n"
        "**运行方式：** scenario registry 展示，不执行实时 OCR 或模型推理。"
    )
    explanation = (
        f"### LoRA {lora_mode}\n\n"
        f"{scenario_explanation(scenario, lora_mode)}\n\n"
        "LoRA 只切换解释文本，不改变风险等级、审计结果或建议动作。"
    )
    trace = {
        "execution_id": execution_id,
        "status": "已完成审计",
        "case_id": case_id,
        "scenario_id": scenario.scenario_id,
        "image_path": scenario.image_path,
        "image_scenario_id": image_scenario_id,
        "ocr_scenario_id": ocr_scenario_id,
        "audit_scenario_id": audit_scenario_id,
        "explanation_scenario_id": explanation_scenario_id,
        "scenario_source": "scenario_registry",
        "realtime_ocr": False,
        "state_sequence": ["已加载", "已展示OCR", "已完成审计"],
        "field_confirmation_status": "已识别",
        "audit_engine_used": "scenario_rule_flow",
        "lora_mode": lora_mode,
        "risk_level": scenario.risk_level,
        "recommended_action": scenario.recommended_action,
        "risk_action_source": "preset_rule_template",
        "lora_affects_decision": False,
    }
    report = {
        "execution_id": execution_id,
        "state": "已完成审计",
        "scenario_id": scenario.scenario_id,
        "risk_level": scenario.risk_level,
        "recommended_action": scenario.recommended_action,
        "audit_result": scenario.audit_result,
        "rules": scenario_rule_rows(scenario),
        "explanation": scenario_explanation(scenario, lora_mode),
    }
    mapping_payload = scenario_mapping_payload(execution_id, scenario)
    return (
        status,
        _risk_zh(scenario.risk_level),
        _action_zh(scenario.recommended_action),
        _scenario_result_card(execution_id, scenario, lora_mode),
        explanation,
        trace,
        report,
        scenario_rule_rows(scenario),
        scenario_evidence_rows(scenario),
        scenario_field_rows(scenario),
        mapping_payload,
    )


def _run_path_b_for_ui(
    service: DemoService,
    catalog: dict[str, dict[str, Any]],
    case_id: str,
    explanation_view: str,
) -> tuple[Any, ...]:
    """Path B：用预置/离线结果演示 image -> candidates -> confirmation -> audit。"""

    mode = _explanation_view_to_mode(catalog, case_id, explanation_view)
    result = service.run_case(case_id, mode)
    case = catalog[case_id]
    confirmation_note = (
        "\n\n### Field Confirmation\n"
        "LayoutLMv3 只提供字段候选；人工确认后的 `confirmed_fields` 才能进入审核。"
        "置信度不会改变风险等级或建议动作。"
    )
    return (
        render_completed_status(case, result),
        _risk_zh(result.risk_level),
        _action_zh(result.recommended_action),
        _result_card_markdown(case, result, explanation_view),
        render_explanation(case, result) + confirmation_note,
        _case_trace(result, explanation_view),
        result.audit_report,
        case["match_rows"],
        case["evidence_rows"],
    )


def _render_explanation_view(selection: str) -> tuple[str, dict[str, Any]]:
    """Explanation Layer：切换 Template / LoRA / Auto Guarded 视图。"""

    service = DemoService()
    if selection == "模板解释":
        result = service.run_case("normal_invoice", "template")
        title = "模板解释"
        note = "固定规则生成，永远可用，是所有模型失败时的回退基线。"
    elif selection == "LoRA 增强解释":
        result = service.run_case("normal_invoice", "experimental_guard_pass")
        title = "LoRA 增强解释"
        note = (
            "LoRA 只润色模板表达，让说明更自然；风险等级、建议动作和判断原因不允许被修改。"
        )
    else:
        result = service.run_case("vendor_name_mismatch", "experimental_guard_fail")
        title = "自动守卫模式"
        note = (
            "如果 LoRA 改写不合规，Guard 会拦截并自动回退模板；审核结果仍来自确定性规则。"
        )
    markdown = (
        f"### {title}\n"
        f"{note}\n\n"
        f"**风险等级：** {_risk_zh(result.risk_level)}  \n"
        f"**建议动作：** {_action_zh(result.recommended_action)}  \n"
        f"**解释来源：** `{result.explanation_source}`  \n"
        f"**Guard 是否通过：** `{str(result.guard_passed).lower()}`  \n"
        f"**回退原因：** `{result.fallback_reason or '无'}`\n\n"
        f"{result.explanation_text}"
    )
    trace = {
        "view": selection,
        "lora_affects_decision": False,
        "risk_level": result.risk_level,
        "recommended_action": result.recommended_action,
        "explanation_source": result.explanation_source,
        "used_rewrite": result.used_rewrite,
        "guard_passed": result.guard_passed,
        "fallback_reason": result.fallback_reason,
        "raw_rewrite_output": result.raw_rewrite_output,
    }
    return markdown, trace


def build_app(service: DemoService | None = None) -> Any:
    """构建流程驱动版 HF Spaces UI。"""

    _require_gradio()
    demo_service = service or DemoService()
    case_catalog = load_invoice_case_catalog()
    initial_path_b = _path_b_preview(case_catalog, "normal_invoice")

    with gr.Blocks(title="ProcureGuard AI", analytics_enabled=False) as app:
        gr.Markdown(
            "# ProcureGuard AI\n"
            "流程驱动的采购发票审核 Demo：Path A 是手动字段快速审核；"
            "Path B 展示发票图片到 AuditReport 的完整交互链路。"
            "风险等级和建议动作始终来自确定性规则，LoRA 只在结果解释里做受控润色。"
        )

        with gr.Tabs(elem_id="unified-portfolio-tabs"):
            with gr.Tab("Path A 手动审核", elem_id="path-a-tab"):
                gr.Markdown(
                    "## Path A: Manual Audit\n\n"
                    "主产品入口：不使用 ML，直接把手动字段和演示用 PO/GRN 上下文送入规则审核引擎。"
                )
                with gr.Row():
                    vendor_name = gr.Textbox(
                        value="Acme Office Supplies",
                        label="供应商",
                        elem_id="path-a-vendor",
                    )
                    invoice_number = gr.Textbox(
                        value="INV-MANUAL-PASS-001",
                        label="发票号",
                        elem_id="path-a-invoice-number",
                    )
                    invoice_date = gr.Textbox(
                        value="2026-06-15",
                        label="发票日期",
                        elem_id="path-a-invoice-date",
                    )
                with gr.Row():
                    total_amount = gr.Number(
                        value=1200.0,
                        label="金额",
                        elem_id="path-a-amount",
                    )
                    currency = gr.Textbox(
                        value="USD",
                        label="货币",
                        elem_id="path-a-currency",
                    )
                    po_number = gr.Textbox(
                        value="PO-MANUAL-1001",
                        label="采购单号",
                        elem_id="path-a-po",
                    )
                    grn_number = gr.Textbox(
                        value="GRN-MANUAL-1001",
                        label="收货单号",
                        elem_id="path-a-grn",
                    )
                duplicate_invoice = gr.Checkbox(
                    value=False,
                    label="模拟重复发票",
                    elem_id="path-a-duplicate",
                )
                path_a_button = gr.Button(
                    "Run Audit",
                    variant="primary",
                    elem_id="path-a-run",
                )
                with gr.Row():
                    path_a_risk = gr.Textbox(label="风险等级", interactive=False)
                    path_a_action = gr.Textbox(label="建议动作", interactive=False)
                path_a_summary = gr.Markdown("结果会显示在这里。", elem_id="path-a-summary")
                with gr.Accordion("AuditReport JSON", open=False):
                    path_a_report = gr.JSON(label="AuditReport JSON")

            with gr.Tab("Path B Scenario Demo", elem_id="path-b-tab"):
                gr.Markdown(
                    "## Path B: AI Vision + 5 Interactive Cases\n\n"
                    "这是 Hugging Face Space 的预置场景流程演示：每张发票图片绑定一个固定 scenario。"
                    "Run Audit 会按 OCR预置结果 → 字段确认 → 规则审计 → LoRA语言增强 的顺序展示，"
                    "不执行实时 OCR 或模型推理。"
                )
                path_b_case_selector = gr.Dropdown(
                    choices=scenario_choices(),
                    value="normal_invoice",
                    label="选择案例",
                    elem_id="demo-case-selector",
                )
                path_b_summary = gr.Markdown(
                    value=initial_path_b[0],
                    elem_id="case-validation-summary",
                )
                with gr.Row():
                    path_b_image = gr.Image(
                        value=initial_path_b[2],
                        label="1. 发票图片",
                        type="filepath",
                        interactive=False,
                        height=420,
                        elem_id="invoice-case-image",
                    )
                    with gr.Column():
                        path_b_image_note = gr.Markdown(
                            value=initial_path_b[1],
                            elem_id="case-image-note",
                        )
                        path_b_status = gr.Markdown(
                            value=initial_path_b[8],
                        elem_id="path-b-run-status",
                    )
                        path_b_run = gr.Button(
                            "Run Audit",
                            variant="primary",
                            elem_id="run-audit-button",
                        )

                with gr.Accordion("2. OCR / LayoutLMv3 字段识别 + 人工确认", open=True):
                    path_b_extraction = gr.Dataframe(
                        value=initial_path_b[3],
                        headers=["字段", "提取值", "置信度", "确认状态", "需要人工确认"],
                        datatype=["str", "str", "number", "str", "bool"],
                        label="OCR 字段表格",
                        interactive=False,
                        wrap=True,
                        elem_id="invoice-case-extraction",
                    )
                    gr.Markdown(
                        "字段未确认仍可进入下一步，但必须带上确认状态；"
                        "本次 execution_id 内的 OCR、审计和解释必须保持一致。"
                    )

                gr.Markdown("## 3. Audit Result", elem_id="path-b-result-anchor")
                with gr.Row():
                    path_b_risk = gr.Textbox(
                        value=initial_path_b[9],
                        label="风险等级",
                        interactive=False,
                        elem_id="main-risk-card",
                    )
                    path_b_action = gr.Textbox(
                        value=initial_path_b[10],
                        label="建议动作",
                        interactive=False,
                        elem_id="main-action-card",
                )
                path_b_result_card = gr.Markdown(
                    value=initial_path_b[7],
                    elem_id="main-result-card",
                )
                path_b_explanation_mode = gr.Radio(
                    choices=["LoRA OFF", "LoRA ON"],
                    value="LoRA OFF",
                    label="LoRA 语言增强",
                    elem_id="case-explanation-mode-selector",
                )
                path_b_explanation = gr.Markdown(
                    value=initial_path_b[8],
                    elem_id="main-final-explanation",
                )
                with gr.Accordion("4. 规则审计说明", open=False):
                    path_b_match = gr.Dataframe(
                        value=initial_path_b[5],
                        headers=["检查项", "情况", "判断"],
                        datatype=["str", "str", "str"],
                        label="三单匹配摘要",
                        interactive=False,
                        wrap=True,
                        elem_id="main-ocr-result",
                    )
                    path_b_evidence = gr.Dataframe(
                        value=initial_path_b[6],
                        headers=["来源", "内容", "说明"],
                        datatype=["str", "str", "str"],
                        label="规则 / 政策证据",
                        interactive=False,
                        wrap=True,
                    )
                with gr.Accordion("Debug: scenario mapping / trace", open=False):
                    path_b_ocr_json = gr.JSON(
                        value=initial_path_b[4],
                        label="Scenario Field Mapping",
                        elem_id="scenario-debug-json",
                    )
                    path_b_trace = gr.JSON(
                        value=initial_path_b[12],
                        label="Trace",
                        elem_id="explanation-layer-trace",
                    )
                    path_b_report = gr.JSON(
                        value=initial_path_b[13],
                        label="AuditReport JSON",
                        elem_id="main-audit-report",
                    )
                with gr.Accordion(
                    "Legacy H1 evidence anchors",
                    open=False,
                    elem_id="e2e-case-technical-details",
                ):
                    gr.Dropdown(
                        choices=[
                            "case_a_standard_pass",
                            "case_b_date_layout_challenge",
                            "case_c_lora_guard_fallback",
                        ],
                        value="case_a_standard_pass",
                        label="H1 evidence case",
                        visible=False,
                        elem_id="e2e-case-selector",
                    )
                    gr.Markdown(
                        "H1 evidence cases are preserved in the repository evidence package.",
                        visible=False,
                    )
                with gr.Accordion(
                    "Synthetic case showcase",
                    open=False,
                    elem_id="synthetic-case-showcase",
                ):
                    gr.Markdown(
                        "Synthetic scenario cases are shown through the current Path B selector.",
                        visible=False,
                    )

            with gr.Tab("系统说明", elem_id="system-explanation-tab"):
                gr.Markdown(
                    "## System Explanation\n\n"
                    "本页只放系统结构、边界和日志说明。LoRA 不再作为单独页面展示；"
                    "它已经移动到 Audit Result 内部的 Explanation Switch。"
                )
                gr.Markdown(ARCHITECTURE_MARKDOWN, elem_id="architecture-summary")
                with gr.Accordion("运行边界", open=False):
                    gr.Markdown(
                        "- Path A 是主产品入口：手动字段、无 ML、快速返回。\n"
                    "- Path B 是 scenario-based deterministic demo：图片绑定唯一 scenario_id。\n"
                    "- OCR 字段不是模型识别结果，而是 scenario 中的固定字段映射。\n"
                    "- LoRA OFF/ON 只切换解释文本，不改变风险等级或建议动作。\n"
                        "- risk_level 和 recommended_action 只能来自确定性规则。"
                    )
                with gr.Accordion("Demo 日志说明", open=False):
                    gr.Markdown(
                        "当前 Space 不上传模型权重，不加载真实 OCR / Qwen / LoRA；"
                        "交互日志以页面 trace 和 AuditReport JSON 展示。"
                    )

        path_a_button.click(
            fn=_run_manual_audit_for_ui,
            inputs=[
                vendor_name,
                invoice_number,
                invoice_date,
                total_amount,
                currency,
                po_number,
                grn_number,
                duplicate_invoice,
            ],
            outputs=[path_a_risk, path_a_action, path_a_summary, path_a_report],
        )
        path_b_case_selector.change(
            fn=lambda selected_case: _path_b_preview(case_catalog, selected_case),
            inputs=[path_b_case_selector],
            outputs=[
                path_b_summary,
                path_b_image_note,
                path_b_image,
                path_b_extraction,
                path_b_ocr_json,
                path_b_match,
                path_b_evidence,
                path_b_result_card,
                path_b_explanation,
                path_b_status,
                path_b_risk,
                path_b_action,
                path_b_trace,
                path_b_report,
            ],
        )
        path_b_run.click(
            fn=lambda selected_case, lora_mode: _run_path_b_scenario_for_ui(
                case_catalog, selected_case, lora_mode
            ),
            inputs=[path_b_case_selector, path_b_explanation_mode],
            outputs=[
                path_b_status,
                path_b_risk,
                path_b_action,
                path_b_result_card,
                path_b_explanation,
                path_b_trace,
                path_b_report,
                path_b_match,
                path_b_evidence,
                path_b_extraction,
                path_b_ocr_json,
            ],
            api_name="run_audit",
        )
    return app


def main() -> None:
    """仅绑定本机启动，不创建 share 链接。"""

    build_app().launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
