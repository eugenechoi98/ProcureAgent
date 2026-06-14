"""构建和启动本地离线 Gradio Demo。"""

from __future__ import annotations

from typing import Any

from demo.architecture_view import build_architecture_tab
from demo.demo_service import DemoOutput, DemoService
from demo.invoice_case_view import (
    case_choices,
    explanation_mode_choices,
    load_invoice_case_catalog,
    preview_values,
    render_completed_status,
    render_explanation,
    render_pending_status,
    render_risk_action,
)
from demo.model_lab_view import build_model_lab_tab

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


def build_app(service: DemoService | None = None) -> Any:
    """只构建页面，不启动服务、不联网、不加载模型。"""

    _require_gradio()
    demo_service = service or DemoService()
    case_catalog = load_invoice_case_catalog()
    initial_preview = preview_values(case_catalog, "normal_invoice")
    with gr.Blocks(
        title="ProcureGuard AI",
        analytics_enabled=False,
    ) as app:
        gr.Markdown(
            "# ProcureGuard AI\n"
            "受控采购发票审核 Agent。发票审核页运行稳定的确定性业务主链；"
            "模型实验和系统架构页展示真实离线证据与工程决策。"
        )
        with gr.Tabs(elem_id="unified-portfolio-tabs"):
            with gr.Tab("发票审核", elem_id="invoice-audit-tab"):
                gr.Markdown(
                    "## 案例演示主页面\n\n"
                    "### 如何看本页\n\n"
                    "1. 先选择一个预置案例，建议从“正常标准发票”开始。  \n"
                    "2. 点击“运行审核”，查看字段抽取、三单匹配、风险等级和建议动作。  \n"
                    "3. 供应商不一致和高风险案例会展示 Guard / fallback 行为。  \n"
                    "4. 完整审核报告和技术输出默认收起，需要核查时再展开。  \n"
                    "5. 公网 Demo 不需要 GPU、API Key 或在线模型。",
                    elem_id="invoice-audit-help",
                )
                with gr.Row():
                    case_selector = gr.Dropdown(
                        choices=case_choices(case_catalog),
                        value="normal_invoice",
                        label="预置发票案例",
                        elem_id="demo-case-selector",
                    )
                    mode_selector = gr.Dropdown(
                        choices=explanation_mode_choices(
                            demo_service.explanation_modes
                        ),
                        value=initial_preview[-1],
                        label="解释模式",
                        elem_id="explanation-mode-selector",
                    )
                gr.Markdown(
                    "解释模式用于演示确定性模板、Guard 和 fallback 行为；"
                    "默认模式由当前案例自动推荐，内部审核规则不会随展示模式改变。",
                    elem_id="explanation-mode-help",
                )
                with gr.Row():
                    run_button = gr.Button(
                        "运行审核", variant="primary", elem_id="run-audit-button"
                    )
                    reset_button = gr.Button("重置", elem_id="reset-demo-button")
                run_status = gr.Markdown(
                    value=render_pending_status(case_catalog["normal_invoice"]),
                    elem_id="invoice-run-status",
                )

                case_brief = gr.Markdown(
                    value=initial_preview[0],
                    elem_id="invoice-case-brief",
                )
                image_note = gr.Markdown(
                    value=initial_preview[1],
                    elem_id="invoice-case-image-note",
                )
                with gr.Row():
                    invoice_image = gr.Image(
                        value=initial_preview[2],
                        label="演示用合成示意图",
                        type="filepath",
                        interactive=False,
                        height=520,
                        elem_id="invoice-case-image",
                    )
                    extraction_comparison = gr.Dataframe(
                        value=initial_preview[3],
                        headers=[
                            "字段",
                            "合成示意真值",
                            "OCR + Regex 基线",
                            "修复后 LayoutLMv3",
                            "证据口径",
                        ],
                        datatype=["str", "str", "str", "str", "str"],
                        label="2. 字段抽取对比（演示案例）",
                        interactive=False,
                        wrap=True,
                        elem_id="invoice-case-extraction",
                    )
                gr.Markdown(
                    "整体 F1 指标请见“模型实验”页；这里展示的是案例级演示对比。",
                    elem_id="invoice-case-f1-note",
                )
                with gr.Row():
                    match_result = gr.Dataframe(
                        value=initial_preview[4],
                        headers=["检查对象", "审核事实", "结果"],
                        datatype=["str", "str", "str"],
                        label="3. 三单匹配结果",
                        interactive=False,
                        wrap=True,
                        elem_id="invoice-case-match",
                    )
                    audit_evidence = gr.Dataframe(
                        value=initial_preview[5],
                        headers=["证据类型", "命中内容", "来源"],
                        datatype=["str", "str", "str"],
                        label="4. 审核证据",
                        interactive=False,
                        wrap=True,
                        elem_id="invoice-case-evidence",
                    )
                with gr.Row():
                    risk_action_story = gr.Markdown(
                        value=initial_preview[6],
                        elem_id="invoice-case-risk-action",
                    )
                    explanation_story = gr.Markdown(
                        value=initial_preview[7],
                        elem_id="invoice-case-explanation",
                    )

                with gr.Accordion(
                    "查看完整技术输出",
                    open=False,
                    elem_id="invoice-audit-technical-output",
                ):
                    status_summary = gr.Markdown(elem_id="demo-status-summary")
                    with gr.Row():
                        case_id = gr.Textbox(label="案例编号", interactive=False)
                        invoice_id = gr.Textbox(
                            label="发票编号", interactive=False
                        )
                        risk_level = gr.Textbox(
                            label="风险等级", interactive=False
                        )
                        recommended_action = gr.Textbox(
                            label="建议动作", interactive=False
                        )
                    with gr.Row():
                        anomaly_types = gr.JSON(label="异常类型")
                        evidence = gr.JSON(label="证据")
                        missing_fields = gr.JSON(label="缺失字段")
                    explanation_text = gr.Textbox(
                        label="审核解释", lines=8, interactive=False
                    )
                    with gr.Row():
                        explanation_source = gr.Textbox(
                            label="解释来源", interactive=False
                        )
                        used_rewrite = gr.Checkbox(
                            label="是否使用改写", interactive=False
                        )
                        guard_passed = gr.Checkbox(
                            label="守卫是否通过", interactive=False
                        )
                        fallback_reason = gr.Textbox(
                            label="回退原因", interactive=False
                        )
                    with gr.Row():
                        facts_hash = gr.Textbox(
                            label="事实哈希", interactive=False
                        )
                        template_version = gr.Textbox(
                            label="模板版本", interactive=False
                        )
                        prompt_version = gr.Textbox(
                            label="提示词版本", interactive=False
                        )
                    with gr.Row():
                        model_version = gr.Textbox(
                            label="模型版本", interactive=False
                        )
                        adapter_version = gr.Textbox(
                            label="Adapter 版本", interactive=False
                        )
                    raw_rewrite_output = gr.Textbox(
                        label="原始改写输出", lines=5, interactive=False
                    )
                    safe_error_summary = gr.Textbox(
                        label="安全回退详情", interactive=False
                    )
                    audit_report = gr.JSON(
                        label="完整审核报告 JSON（AuditReport）"
                    )

            with gr.Tab("模型实验", elem_id="model-lab-tab"):
                build_model_lab_tab(gr)

            with gr.Tab("系统架构", elem_id="architecture-tab"):
                build_architecture_tab(gr)

        technical_outputs = [
            status_summary,
            case_id,
            invoice_id,
            risk_level,
            recommended_action,
            anomaly_types,
            evidence,
            missing_fields,
            explanation_text,
            explanation_source,
            used_rewrite,
            guard_passed,
            fallback_reason,
            facts_hash,
            template_version,
            prompt_version,
            model_version,
            adapter_version,
            raw_rewrite_output,
            safe_error_summary,
            audit_report,
        ]
        case_selector.change(
            fn=lambda selected_case: _preview_for_ui(
                case_catalog, selected_case
            ),
            inputs=[case_selector],
            outputs=[
                case_brief,
                image_note,
                invoice_image,
                extraction_comparison,
                match_result,
                audit_evidence,
                risk_action_story,
                explanation_story,
                run_status,
                mode_selector,
            ],
        )
        run_button.click(
            fn=lambda selected_case, selected_mode: _run_for_ui(
                demo_service, case_catalog, selected_case, selected_mode
            ),
            inputs=[case_selector, mode_selector],
            outputs=[
                run_status,
                risk_action_story,
                explanation_story,
                *technical_outputs,
            ],
            api_name="run_audit",
        )
        reset_button.click(
            fn=lambda: (
                "normal_invoice",
                initial_preview[-1],
                *initial_preview[:-1],
                render_pending_status(case_catalog["normal_invoice"]),
                *([None] * len(technical_outputs)),
            ),
            inputs=[],
            outputs=[
                case_selector,
                mode_selector,
                case_brief,
                image_note,
                invoice_image,
                extraction_comparison,
                match_result,
                audit_evidence,
                risk_action_story,
                explanation_story,
                run_status,
                *technical_outputs,
            ],
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
