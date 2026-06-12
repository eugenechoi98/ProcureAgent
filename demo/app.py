"""构建和启动本地离线 Gradio Demo。"""

from __future__ import annotations

from typing import Any

import gradio as gr

from demo.demo_service import DemoOutput, DemoService


def _summary_markdown(result: DemoOutput) -> str:
    """生成紧凑状态摘要，并明确标记静态 fallback。"""

    path_label = (
        "STATIC FALLBACK" if result.static_fallback else "LIVE HYBRID AUDIT"
    )
    fallback = result.static_fallback_reason or "None"
    return (
        f"### {path_label}\n"
        f"**Case:** `{result.case_id}`  \n"
        f"**Invoice:** `{result.invoice_id}`  \n"
        f"**Risk:** `{result.risk_level}`  \n"
        f"**Action:** `{result.recommended_action}`  \n"
        f"**Demo fallback:** `{fallback}`"
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


def build_app(service: DemoService | None = None) -> gr.Blocks:
    """只构建页面，不启动服务、不联网、不加载模型。"""

    demo_service = service or DemoService()
    with gr.Blocks(
        title="ProcureGuard AI",
        analytics_enabled=False,
    ) as app:
        gr.Markdown(
            "# ProcureGuard AI\n"
            "Local offline audit demo with deterministic template explanations."
        )
        with gr.Row():
            case_selector = gr.Dropdown(
                choices=demo_service.case_ids,
                value="normal_invoice",
                label="Demo Case",
                elem_id="demo-case-selector",
            )
            mode_selector = gr.Dropdown(
                choices=demo_service.explanation_modes,
                value="template",
                label="Explanation Mode",
                elem_id="explanation-mode-selector",
            )
        with gr.Row():
            run_button = gr.Button(
                "运行审核", variant="primary", elem_id="run-audit-button"
            )
            reset_button = gr.Button("重置", elem_id="reset-demo-button")

        status_summary = gr.Markdown(elem_id="demo-status-summary")
        with gr.Row():
            case_id = gr.Textbox(label="Case ID", interactive=False)
            invoice_id = gr.Textbox(label="Invoice ID", interactive=False)
            risk_level = gr.Textbox(label="Risk Level", interactive=False)
            recommended_action = gr.Textbox(
                label="Recommended Action", interactive=False
            )
        with gr.Row():
            anomaly_types = gr.JSON(label="Anomaly Types")
            evidence = gr.JSON(label="Evidence")
            missing_fields = gr.JSON(label="Missing Fields")
        explanation_text = gr.Textbox(
            label="Explanation Text", lines=8, interactive=False
        )
        with gr.Row():
            explanation_source = gr.Textbox(
                label="Explanation Source", interactive=False
            )
            used_rewrite = gr.Checkbox(label="Used Rewrite", interactive=False)
            guard_passed = gr.Checkbox(label="Guard Passed", interactive=False)
            fallback_reason = gr.Textbox(
                label="Fallback Reason", interactive=False
            )
        with gr.Row():
            facts_hash = gr.Textbox(label="Facts Hash", interactive=False)
            template_version = gr.Textbox(
                label="Template Version", interactive=False
            )
            prompt_version = gr.Textbox(
                label="Prompt Version", interactive=False
            )
        with gr.Row():
            model_version = gr.Textbox(label="Model Version", interactive=False)
            adapter_version = gr.Textbox(
                label="Adapter Version", interactive=False
            )
        raw_rewrite_output = gr.Textbox(
            label="Raw Rewrite Output", lines=5, interactive=False
        )
        safe_error_summary = gr.Textbox(
            label="Safe Fallback Detail", interactive=False
        )
        audit_report = gr.JSON(label="Complete AuditReport JSON")

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
            api_name=False,
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
