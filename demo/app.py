"""构建和启动本地离线 Gradio Demo。"""

from __future__ import annotations

from typing import Any

from demo.architecture_view import build_architecture_tab
from demo.demo_service import DemoOutput, DemoService
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
    service: DemoService, case_id: str, explanation_mode: str
) -> tuple[Any, ...]:
    """把 service 输出转换为 Gradio 组件值。"""

    result = service.run_case(case_id, explanation_mode)
    return (
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


def build_app(service: DemoService | None = None) -> Any:
    """只构建页面，不启动服务、不联网、不加载模型。"""

    _require_gradio()
    demo_service = service or DemoService()
    with gr.Blocks(
        title="ProcureGuard AI",
        analytics_enabled=False,
    ) as app:
        gr.Markdown(
            "# ProcureGuard AI\n"
            "采购发票智能审核 Agent 演示。发票审核页运行稳定的离线业务主链；"
            "模型实验和系统架构页展示真实离线证据与工程决策。"
        )
        with gr.Tabs(elem_id="unified-portfolio-tabs"):
            with gr.Tab("发票审核", elem_id="invoice-audit-tab"):
                gr.Markdown(
                    "### 如何使用\n\n"
                    "1. 保持默认案例 `normal_invoice` 和默认解释模式 `template`。\n"
                    "2. 点击“运行审核”。\n"
                    "3. 查看风险等级、建议动作、异常类型、证据和审核解释。\n"
                    "4. 下方 JSON 是完整审核报告，方便技术面试官核查结构化输出。\n"
                    "5. 这里运行的是稳定的离线业务主链，不需要 GPU、API Key 或在线模型。",
                    elem_id="invoice-audit-help",
                )
                with gr.Row():
                    case_selector = gr.Dropdown(
                        choices=demo_service.case_ids,
                        value="normal_invoice",
                        label="演示案例",
                        elem_id="demo-case-selector",
                    )
                    mode_selector = gr.Dropdown(
                        choices=demo_service.explanation_modes,
                        value="template",
                        label="解释模式",
                        elem_id="explanation-mode-selector",
                    )
                with gr.Row():
                    run_button = gr.Button(
                        "运行审核", variant="primary", elem_id="run-audit-button"
                    )
                    reset_button = gr.Button("重置", elem_id="reset-demo-button")

                status_summary = gr.Markdown(elem_id="demo-status-summary")
                with gr.Row():
                    case_id = gr.Textbox(label="案例编号", interactive=False)
                    invoice_id = gr.Textbox(label="发票编号", interactive=False)
                    risk_level = gr.Textbox(label="风险等级", interactive=False)
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
                    facts_hash = gr.Textbox(label="事实哈希", interactive=False)
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
                audit_report = gr.JSON(label="完整审核报告 JSON（AuditReport）")

            with gr.Tab("模型实验", elem_id="model-lab-tab"):
                build_model_lab_tab(gr)

            with gr.Tab("系统架构", elem_id="architecture-tab"):
                build_architecture_tab(gr)

        outputs = [
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
        run_button.click(
            fn=lambda selected_case, selected_mode: _run_for_ui(
                demo_service, selected_case, selected_mode
            ),
            inputs=[case_selector, mode_selector],
            outputs=outputs,
            api_name="run_audit",
        )
        reset_button.click(
            fn=lambda: ("normal_invoice", "template", *([None] * len(outputs))),
            inputs=[],
            outputs=[case_selector, mode_selector, *outputs],
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
