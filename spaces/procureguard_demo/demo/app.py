"""构建和启动本地离线 Gradio Demo。"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from urllib.parse import quote
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
DEMO_VIDEO_PATH = DEMO_ROOT / "assets" / "videos" / "procureguard_full_pipeline_demo.mp4"
GITHUB_URL = "https://github.com/eugenechoi98/ProcureAgent"
HF_SPACE_URL = "https://huggingface.co/spaces/eugene-98/procureguard-ai-demo"

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


def _register_static_assets() -> None:
    """把静态资源交给浏览器直接读取，避免 Gradio 初始化时复制或转码。"""

    if gr is not None and hasattr(gr, "set_static_paths"):
        gr.set_static_paths(DEMO_ROOT / "assets")


def _static_file_url(path: Path) -> str:
    """生成 Gradio 静态文件 URL。"""

    return f"/gradio_api/file={quote(path.resolve().as_posix(), safe='/:')}"


def _video_player_html() -> str:
    """第三页视频：使用原生 HTML video，避免 gr.Video 冷启动转码。"""

    if not DEMO_VIDEO_PATH.is_file():
        return """
<div id="full-pipeline-video-placeholder" style="border:1px solid #e5e7eb;border-radius:12px;padding:18px;background:#fff7ed;">
  <strong>视频暂未打包到 Space。</strong><br>
  请检查 <code>demo/assets/videos/procureguard_full_pipeline_demo.mp4</code>。
  页面会继续展示文字说明，不会因为资源缺失阻塞启动。
</div>
"""
    video_url = escape(_static_file_url(DEMO_VIDEO_PATH), quote=True)
    return f"""
<div id="full-pipeline-video" style="border:1px solid #e5e7eb;border-radius:12px;padding:12px;background:#ffffff;">
  <video controls preload="metadata" style="width:100%;max-height:720px;border-radius:10px;background:#111;">
    <source src="{video_url}" type="video/mp4">
    当前浏览器无法直接播放该 MP4。请在 GitHub 或本地 Demo 中查看完整录屏。
  </video>
  <p style="margin:10px 0 0;color:#4b5563;font-size:14px;">
    视频为静态浏览器播放资源；Space 启动阶段不会加载模型，也不会执行视频转码。
  </p>
</div>
"""


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
        "### Path A 审核结果\n"
        f"**风险等级：** `{_risk_zh(response.risk_level)}`  \n"
        f"**建议动作：** `{_action_zh(response.recommended_action)}`  \n"
        "**决策来源：** `确定性规则`  \n"
        "**是否使用模型：** `否`  \n"
        "**是否具备付款权限：** `否`"
    )
    explanation = (
        "### 审核解释\n"
        f"{response.audit_report.explanation.explanation_text if response.audit_report.explanation else response.audit_report.anomaly_explanation}\n\n"
        "Path A 不使用 LoRA；审核结论由确定性规则引擎生成。"
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


def _product_overview_markdown() -> str:
    """第一页：让面试官快速理解产品、模型和安全边界。"""

    return f"""
# ProcureGuard AI

**ProcureGuard AI 是一个受控采购发票审核 Agent。**<br>
它把发票图片理解、PO/GRN 采购上下文、三单匹配、重复检测、风险规则和解释层串成一个可审计的 `AuditReport`。

## 这是什么产品

ProcureGuard AI 用来演示一个真实采购发票审核系统的核心闭环：

```text
发票图片
-> OCR 文本与 bbox 坐标
-> LayoutLMv3 字段候选抽取
-> 人工确认后的字段
-> PO / GRN 采购上下文查询
-> 确定性审核规则
-> AuditReport 审核报告
-> 模板解释
-> 可选 LoRA 改写 + Guard / 模板回退
```

核心原则很简单：**AI 负责读票和润色解释，规则负责风险决策。**

## 我用 LayoutLMv3 做了什么

- 使用 PyTorch / Transformers 微调 LayoutLMv3，处理 SROIE 发票字段抽取。
- 输入不是普通文本，而是 OCR token、bbox 坐标和文档版面信息。
- 输出 company、date、total、address 等字段候选，再映射成审核需要的供应商、日期和金额。
- 做过 OCR + Regex baseline、字段级 F1、错误分析和字段重建优化。
- Date 字段从容易混入 `Date:`、时间和旁边文本，优化到更稳定的日期 span reconstruction。

公开 Space 不在线加载 LayoutLMv3 权重；真实本地运行流程见第三页视频。

## 审核系统怎么做决策

- PO 匹配、GRN 匹配、金额一致性、重复发票检测都由确定性规则完成。
- “风险等级”和“建议动作”不由 LayoutLMv3、LoRA 或任何大模型决定。
- 采购上下文在 Demo 中使用 mock PO/GRN，用来展示真实业务链路，不代表企业 ERP 数据。
- AuditReport 是审核说明，不是付款凭证。

## LoRA 怎么用，失败怎么兜底

LoRA 是 Qwen2.5-0.5B 的受控解释改写候选，只作用在审核结果之后：

```text
确定性模板解释
-> LoRA 改写候选
-> Guard 检查事实 / 风险 / 动作
-> 通过：展示增强解释
-> 失败：回退模板解释
```

如果 LoRA 输出空、格式不对、改了风险等级、改了建议动作、编造 PO/GRN 或金额，Guard 会拒绝它。<br>
这个回退机制是产品安全设计，不是演示失败。

## 产品亮点

- 真实 LayoutLMv3 微调和字段抽取实验，不只是套 OCR。
- 图片字段、采购上下文、规则审核、解释层形成完整闭环。
- 模型职责受控：模型不越权做财务判断。
- Scenario Demo 可在公网稳定交互；本地视频展示真实 OCR/LayoutLMv3 + LoRA 运行链路。
- GitHub 仓库保留 README、Quickstart、报告、测试和边界说明。

**GitHub:** [{GITHUB_URL}]({GITHUB_URL})<br>
**Hugging Face Space:** [{HF_SPACE_URL}]({HF_SPACE_URL})
"""


def _video_intro_markdown() -> str:
    """第三页：解释视频展示的本地真实链路。"""

    return """
## 完整流程视频

这个视频展示的是本地完整运行链路。公网页面为了保证访问稳定，只做轻量的预置案例演示；视频里展示的是本地真实模型链路。

```text
上传发票图片
-> OCR 文本识别
-> LayoutLMv3 字段抽取
-> 演示用 PO / GRN 采购上下文查询
-> 第二阶段确定性规则审核
-> 受控 LoRA 解释候选
-> 必要时回退模板解释
```

为什么公网页面不直接跑完整模型：

- LayoutLMv3 检查点、Qwen 基座模型和 LoRA 适配器都是大文件，不适合直接放进 CPU 版 Space。
- 公网 Space 冷启动和内存限制会影响面试演示稳定性。
- 视频负责展示真实本地完整链路；公网页面负责快速打开、稳定交互和解释系统边界。
"""


def _project_links_markdown() -> str:
    """第四页：项目入口、运行方式和边界说明。"""

    return f"""
## 项目入口

- GitHub 仓库：[{GITHUB_URL}]({GITHUB_URL})
- Hugging Face 展示页：[{HF_SPACE_URL}]({HF_SPACE_URL})
- 开源快速启动：`docs/OPEN_SOURCE_QUICKSTART.md`
- 隐私与数据边界：`docs/PRIVACY_AND_DATA_BOUNDARIES.md`
- 完整架构说明：`ARCHITECTURE.md`

## 公网页面实际运行什么

- Scenario 驱动的确定性演示界面。
- 手动字段审核流程，使用显式 mock PO/GRN 上下文。
- 5 个可交互案例，每个案例都有发票图片、Run Audit 按钮和结果卡片。
- LoRA OFF / ON 只作为解释文本切换，不参与审核决策。

## 本地完整链路实际运行什么

- 真实本地 OCR / LayoutLMv3 字段抽取。
- Demo PO/GRN mock context 自动查询。
- 已有 Phase 2 确定性审核引擎。
- 配置本地模型资产后，可调用受控 LoRA provider 生成解释候选。

## 运行边界

- 公网页面不做付款决策。
- 公网页面不连接 ERP，也不处理真实敏感企业发票。
- 公网页面不在线加载 LayoutLMv3、Qwen 或 LoRA 权重。
- “风险等级”和“建议动作”始终由规则生成。
"""


def _architecture_diagram_html() -> str:
    """用 SVG 渲染中文系统架构图，避免 Mermaid 源码裸露。"""

    return """
<div style="overflow-x:auto; padding: 8px 0;">
  <svg width="1180" height="390" viewBox="0 0 1180 390" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ProcureGuard AI 系统架构图">
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#2563eb" />
      </marker>
      <style>
        .box { fill: #eff6ff; stroke: #2563eb; stroke-width: 1.6; rx: 12; }
        .safe { fill: #ecfdf5; stroke: #059669; stroke-width: 1.6; rx: 12; }
        .warn { fill: #fff7ed; stroke: #ea580c; stroke-width: 1.6; rx: 12; }
        .fallback { fill: #f8fafc; stroke: #64748b; stroke-width: 1.6; rx: 12; }
        .title { font: 700 16px Arial, 'Microsoft YaHei', sans-serif; fill: #0f172a; }
        .text { font: 13px Arial, 'Microsoft YaHei', sans-serif; fill: #334155; }
        .small { font: 12px Arial, 'Microsoft YaHei', sans-serif; fill: #475569; }
        .line { stroke: #2563eb; stroke-width: 2; fill: none; marker-end: url(#arrow); }
        .guard { stroke: #ea580c; stroke-width: 2; fill: none; marker-end: url(#arrow); }
      </style>
    </defs>

    <text x="20" y="28" class="title">ProcureGuard AI 端到端审核链路</text>
    <text x="20" y="50" class="small">模型负责读票和解释增强；风险等级与建议动作只由确定性规则生成。</text>

    <rect class="box" x="20" y="85" width="130" height="72" />
    <text x="85" y="114" text-anchor="middle" class="title">发票图片</text>
    <text x="85" y="138" text-anchor="middle" class="small">用户上传 / 示例图</text>

    <rect class="box" x="185" y="85" width="145" height="72" />
    <text x="258" y="114" text-anchor="middle" class="title">OCR 结果</text>
    <text x="258" y="138" text-anchor="middle" class="small">文本 + bbox 坐标</text>

    <rect class="box" x="365" y="85" width="165" height="72" />
    <text x="448" y="111" text-anchor="middle" class="title">LayoutLMv3</text>
    <text x="448" y="135" text-anchor="middle" class="small">字段候选抽取</text>
    <text x="448" y="151" text-anchor="middle" class="small">不做风险判断</text>

    <rect class="warn" x="565" y="85" width="150" height="72" />
    <text x="640" y="112" text-anchor="middle" class="title">字段确认层</text>
    <text x="640" y="136" text-anchor="middle" class="small">人工确认 / 修正</text>

    <rect class="safe" x="750" y="85" width="160" height="72" />
    <text x="830" y="111" text-anchor="middle" class="title">采购上下文</text>
    <text x="830" y="135" text-anchor="middle" class="small">PO / GRN mock 查询</text>

    <rect class="safe" x="945" y="85" width="180" height="72" />
    <text x="1035" y="107" text-anchor="middle" class="title">确定性审核引擎</text>
    <text x="1035" y="131" text-anchor="middle" class="small">三单匹配 / 重复检测</text>
    <text x="1035" y="148" text-anchor="middle" class="small">生成风险与建议动作</text>

    <path class="line" d="M150 121 H185" />
    <path class="line" d="M330 121 H365" />
    <path class="line" d="M530 121 H565" />
    <path class="line" d="M715 121 H750" />
    <path class="line" d="M910 121 H945" />

    <rect class="safe" x="120" y="235" width="170" height="78" />
    <text x="205" y="263" text-anchor="middle" class="title">AuditReport</text>
    <text x="205" y="288" text-anchor="middle" class="small">风险等级 / 建议动作</text>

    <rect class="fallback" x="345" y="235" width="165" height="78" />
    <text x="428" y="263" text-anchor="middle" class="title">模板解释</text>
    <text x="428" y="288" text-anchor="middle" class="small">默认、安全、永远可用</text>

    <rect class="warn" x="565" y="235" width="165" height="78" />
    <text x="648" y="263" text-anchor="middle" class="title">LoRA 改写候选</text>
    <text x="648" y="288" text-anchor="middle" class="small">只润色解释文本</text>

    <rect class="warn" x="785" y="235" width="130" height="78" />
    <text x="850" y="263" text-anchor="middle" class="title">Guard 校验</text>
    <text x="850" y="288" text-anchor="middle" class="small">禁止改事实/结论</text>

    <rect class="safe" x="970" y="205" width="155" height="62" />
    <text x="1048" y="232" text-anchor="middle" class="title">增强解释</text>
    <text x="1048" y="252" text-anchor="middle" class="small">Guard PASS</text>

    <rect class="fallback" x="970" y="300" width="155" height="62" />
    <text x="1048" y="327" text-anchor="middle" class="title">模板回退</text>
    <text x="1048" y="347" text-anchor="middle" class="small">Guard FAIL</text>

    <path class="line" d="M1035 157 V185 C1035 210 205 207 205 235" />
    <path class="line" d="M290 274 H345" />
    <path class="line" d="M510 274 H565" />
    <path class="guard" d="M730 274 H785" />
    <path class="guard" d="M915 260 C940 250 945 236 970 236" />
    <path class="guard" d="M915 288 C940 300 945 331 970 331" />
  </svg>
</div>
"""


def build_app(service: DemoService | None = None) -> Any:
    """构建流程驱动版 HF Spaces UI。"""

    _require_gradio()
    _register_static_assets()
    demo_service = service or DemoService()
    case_catalog = load_invoice_case_catalog()
    initial_path_b = _path_b_preview(case_catalog, "normal_invoice")

    with gr.Blocks(title="ProcureGuard AI", analytics_enabled=False) as app:
        gr.Markdown(
            "# ProcureGuard AI\n"
            "受控采购发票审核 Agent：AI 负责读票和解释增强，"
            "风险等级与建议动作始终由确定性规则生成。"
        )

        with gr.Tabs(elem_id="unified-portfolio-tabs"):
            with gr.Tab("产品总览", elem_id="product-overview-tab"):
                gr.Markdown(_product_overview_markdown(), elem_id="product-overview")
                with gr.Accordion("系统架构图", open=True):
                    gr.HTML(_architecture_diagram_html(), elem_id="architecture-diagram")

            with gr.Tab("Scenario Demo", elem_id="path-b-tab"):
                gr.Markdown(
                    "## Scenario Demo\n\n"
                    "公网 Space 使用稳定的预置案例驱动演示：每张发票图片绑定唯一案例。"
                    "点击 Run Audit 后，页面按字段展示 → 字段确认 → 规则审计 → LoRA解释切换的顺序展示。"
                    "这里不执行实时 LayoutLMv3；真实本地运行请看第三页视频。"
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

            with gr.Tab("完整流程视频", elem_id="full-pipeline-video-tab"):
                gr.Markdown(_video_intro_markdown(), elem_id="video-intro")
                gr.Markdown(
                    "### 视频里应该重点看什么\n\n"
                    "1. 上传真实 SROIE 发票图片。\n"
                    "2. LayoutLMv3 抽出发票号、供应商和金额。\n"
                    "3. 系统自动查询演示用 PO / GRN 采购上下文。\n"
                    "4. 第二阶段确定性审核输出风险等级和建议动作。\n"
                    "5. LoRA 只作为解释层候选；Guard 失败会回退模板。"
                )
                gr.HTML(_video_player_html(), elem_id="full-pipeline-video-html")

            with gr.Tab("GitHub / 运行边界", elem_id="system-explanation-tab"):
                gr.Markdown(
                    _project_links_markdown(),
                    elem_id="project-links",
                )
                gr.Markdown(ARCHITECTURE_MARKDOWN, elem_id="architecture-summary")
                with gr.Accordion("运行边界", open=False):
                    gr.Markdown(
                    "- Path A 是主产品入口：手动字段、不使用模型、快速返回。\n"
                        "- Path B 是预置案例驱动的确定性演示：图片绑定唯一 scenario_id。\n"
                        "- OCR 字段不是公网实时模型识别结果，而是预置案例中的固定字段映射。\n"
                        "- LoRA OFF/ON 只切换解释文本，不改变风险等级或建议动作。\n"
                        "- 风险等级和建议动作只能来自确定性规则。"
                    )
                with gr.Accordion("Demo 日志说明", open=False):
                    gr.Markdown(
                        "当前 Space 不上传模型权重，不加载真实 OCR / Qwen / LoRA；"
                        "交互日志以页面追踪信息和 AuditReport JSON 展示。"
                    )
                with gr.Accordion("辅助入口：Path A 手动审核", open=False):
                    gr.Markdown(
                        "Path A 是偏产品化的快速审核入口：不使用模型，"
                        "直接把手动字段和演示 PO/GRN 上下文送入规则审核引擎。"
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
                    path_a_summary = gr.Markdown(
                        "结果会显示在这里。",
                        elem_id="path-a-summary",
                    )
                    with gr.Accordion("AuditReport JSON", open=False):
                        path_a_report = gr.JSON(label="AuditReport JSON")

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
