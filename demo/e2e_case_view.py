"""读取 H0 证据包，并构建端到端案例只读展示。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEMO_ROOT = Path(__file__).resolve().parent
EVIDENCE_ROOT = DEMO_ROOT / "e2e_cases"

CASE_LABELS = {
    "case_a_standard_pass": "案例 A：标准发票，字段抽取准确，审核通过",
    "case_b_date_layout_challenge": "案例 B：日期版式挑战，展示日期清理与重建",
    "case_c_lora_guard_fallback": "案例 C：LoRA 幻觉与 Guard 拦截回退",
}


def load_e2e_case_catalog(
    root: Path = EVIDENCE_ROOT,
) -> dict[str, dict[str, Any]]:
    """加载三个已验收证据包，不执行模型推理。"""

    catalog: dict[str, dict[str, Any]] = {}
    for case_id in CASE_LABELS:
        case_root = root / case_id
        manifest = _read_json(case_root / "manifest.json")
        payload: dict[str, Any] = {
            "case_id": case_id,
            "display_name": CASE_LABELS[case_id],
            "root": case_root,
            "manifest": manifest,
        }
        if case_id in {
            "case_a_standard_pass",
            "case_b_date_layout_challenge",
        }:
            payload.update(
                {
                    "extracted_fields": _read_json(
                        case_root / "extracted_fields.json"
                    ),
                    "phase2_input": _read_json(
                        case_root / "phase2_audit_input.json"
                    ),
                    "phase2_result": _read_json(
                        case_root / "phase2_audit_result.json"
                    ),
                }
            )
            if case_id == "case_b_date_layout_challenge":
                payload["date_reconstruction"] = _read_json(
                    case_root / "date_reconstruction.json"
                )
        else:
            payload.update(
                {
                    "audit_facts": _read_json(case_root / "audit_facts.json"),
                    "guard_result": _read_json(case_root / "guard_result.json"),
                    "final_audit_report": _read_json(
                        case_root / "final_audit_report.json"
                    ),
                    "lora_raw_output": (
                        case_root / "lora_raw_output.txt"
                    ).read_text(encoding="utf-8"),
                    "final_explanation": (
                        case_root / "final_explanation.md"
                    ).read_text(encoding="utf-8"),
                }
            )
        catalog[case_id] = payload
    return catalog


def e2e_case_choices(
    catalog: dict[str, dict[str, Any]],
) -> list[tuple[str, str]]:
    """返回稳定的端到端案例选项。"""

    return [(case["display_name"], case_id) for case_id, case in catalog.items()]


def e2e_case_values(case: dict[str, Any]) -> tuple[Any, ...]:
    """将单个证据包转换为页面组件值。"""

    if case["case_id"] == "case_c_lora_guard_fallback":
        return _guard_case_values(case)
    return _invoice_case_values(case)


def build_e2e_case_showcase(gr: Any) -> None:
    """构建 H1 主案例区，选择案例后直接展示已提交证据。"""

    catalog = load_e2e_case_catalog()
    initial = e2e_case_values(catalog["case_a_standard_pass"])

    gr.Markdown(
        "## 端到端真实证据链\n\n"
        "### 如何看本页\n\n"
        "1. 先选择案例，建议从案例 A 开始。  \n"
        "2. A/B 串起公开数据集图片、离线 checkpoint 字段预测和 Phase 2 审核结果。  \n"
        "3. C 展示真实离线 LoRA 输出如何被 Guard 拒绝并回退到确定性模板。  \n"
        "4. 页面读取 H0 已验收证据包，不在公网运行模型，也不上传模型权重。  \n"
        "5. 整个 Demo 不需要 GPU、API Key 或在线模型。",
        elem_id="e2e-case-help",
    )
    selector = gr.Dropdown(
        choices=e2e_case_choices(catalog),
        value="case_a_standard_pass",
        label="端到端证据链案例",
        elem_id="e2e-case-selector",
    )
    summary = gr.Markdown(initial[0], elem_id="e2e-case-summary")
    source_note = gr.Markdown(initial[1], elem_id="e2e-case-source-note")
    image_gallery = gr.Gallery(
        value=initial[2],
        label="原图、OCR 与 LayoutLMv3 证据",
        columns=3,
        rows=1,
        object_fit="contain",
        height=420,
        elem_id="e2e-case-image-gallery",
    )
    extraction_note = gr.Markdown(
        initial[3], elem_id="e2e-case-extraction-note"
    )
    extraction_table = gr.Dataframe(
        value=initial[4],
        headers=["字段", "参考值 / 审核事实", "模型结果 / 证据值", "来源边界"],
        datatype=["str", "str", "str", "str"],
        label="字段抽取与事实对照",
        interactive=False,
        wrap=True,
        elem_id="e2e-case-extraction-table",
    )
    with gr.Row():
        match_table = gr.Dataframe(
            value=initial[5],
            headers=["检查项", "结果", "证据边界"],
            datatype=["str", "str", "str"],
            label="三单匹配与重复检查",
            interactive=False,
            wrap=True,
            elem_id="e2e-case-match-table",
        )
        evidence_table = gr.Dataframe(
            value=initial[6],
            headers=["证据类型", "结论", "来源"],
            datatype=["str", "str", "str"],
            label="审核证据",
            interactive=False,
            wrap=True,
            elem_id="e2e-case-evidence-table",
        )
    with gr.Row():
        risk_action = gr.Markdown(
            initial[7], elem_id="e2e-case-risk-action"
        )
        explanation = gr.Markdown(
            initial[8], elem_id="e2e-case-explanation"
        )
    with gr.Accordion(
        "查看证据包原始结构",
        open=False,
        elem_id="e2e-case-technical-details",
    ):
        technical_primary = gr.JSON(
            value=initial[9],
            label="主要输入 / 规范化审核事实",
            elem_id="e2e-case-technical-primary",
        )
        technical_result = gr.JSON(
            value=initial[10],
            label="Phase 2 / Guard 结果",
            elem_id="e2e-case-technical-result",
        )
        raw_output = gr.Textbox(
            value=initial[11],
            label="真实离线 LoRA 原始输出（仅案例 C）",
            lines=6,
            interactive=False,
            elem_id="e2e-case-raw-output",
        )
        manifest = gr.JSON(
            value=initial[12],
            label="证据 manifest 与 SHA-256",
            elem_id="e2e-case-manifest",
        )

    selector.change(
        fn=lambda case_id: e2e_case_values(catalog[case_id]),
        inputs=[selector],
        outputs=[
            summary,
            source_note,
            image_gallery,
            extraction_note,
            extraction_table,
            match_table,
            evidence_table,
            risk_action,
            explanation,
            technical_primary,
            technical_result,
            raw_output,
            manifest,
        ],
    )


def _invoice_case_values(case: dict[str, Any]) -> tuple[Any, ...]:
    manifest = case["manifest"]
    fields = case["extracted_fields"]
    phase2_input = case["phase2_input"]
    result = case["phase2_result"]
    case_root = case["root"]
    prediction = fields["prediction"]
    ground_truth = fields["ground_truth"]
    provenance = {
        "company": "offline_real_layoutlmv3_checkpoint_prediction",
        "address": "offline_real_layoutlmv3_checkpoint_prediction",
        "date": "offline_real_layoutlmv3_checkpoint_prediction",
        "total": "offline_real_layoutlmv3_checkpoint_prediction",
    }
    date_note = ""
    if "date_reconstruction" in case:
        reconstruction = case["date_reconstruction"]
        date_note = (
            "\n\n**日期重建：** "
            f"`{reconstruction['legacy_date']}` → "
            f"`{reconstruction['cleaned_date']}`。"
            "这是单样本证据；整体 Date F1 请见“模型实验”页。"
        )

    summary = (
        f"### {case['display_name']}\n\n"
        f"样本编号：`{manifest['source_sample_id']}`。"
        "图片、OCR 框和 LayoutLMv3 预测通过同一 sample_id 对齐；"
        "之后把离线预测字段送入现有 Phase 2 确定性审核链。"
    )
    source_note = (
        "**图片来源与公开边界：** SROIE validation 样本，来源 "
        "Voxel51/scanned_receipts（衍生自 ICDAR 2019 SROIE），"
        "按数据集卡标注为 CC BY 4.0。人工复核仅发现企业地址、电话和订单信息，"
        "未发现可识别的自然人客户姓名，因此本次不做遮罩并保留归属说明。"
    )
    gallery = [
        (str(case_root / "source_invoice.png"), "SROIE 原始图片"),
        (str(case_root / "ocr_boxes.png"), "OCR words / bbox"),
        (
            str(case_root / "layoutlmv3_predictions.png"),
            "LayoutLMv3 离线 checkpoint 预测",
        ),
    ]
    extraction_note = (
        "### LayoutLMv3 字段抽取（离线 checkpoint 真实推理结果）\n\n"
        "`official_test=false`。这里是案例级可追溯证据，不代表单图能够证明"
        f"整体模型指标。{date_note}"
    )
    extraction_rows = [
        [
            field,
            ground_truth.get(field, "无"),
            prediction.get(field, "无"),
            provenance[field],
        ]
        for field in ("company", "address", "date", "total")
    ]
    match_rows = [
        ["采购订单（PO）", _yes_no(result["po_match"]), "mock PO 上下文"],
        [
            "收货单（GRN）",
            _yes_no(result["goods_receipt_match"]),
            "mock GRN 上下文",
        ],
        ["发票", result["invoice_id"], "编号为演示关联标识，不来自图片抽取"],
        ["重复检查", "通过", "现有 Phase 2 确定性检查"],
    ]
    evidence_rows = [
        ["政策 RAG", "未命中异常政策", "现有 Phase 2 审核结果"],
        ["风险规则", "PO、GRN、金额、重复与政策检查均通过", "确定性规则链"],
        [
            "上下文边界",
            "PO / GRN 为明确标注的 mock 采购上下文",
            "不是企业真实采购系统数据",
        ],
    ]
    risk_action = (
        "### 风险等级与建议动作\n\n"
        f"**风险等级：** {_risk_label(result['risk_level'])}  \n"
        f"**建议动作：** {_action_label(result['recommended_action'])}  \n"
        "该结果由已提交的 Phase 2 真实运行证据生成。"
    )
    explanation = (
        "### 最终审核解释\n\n"
        f"{result['explanation']['explanation_text']}\n\n"
        "**正式输出来源：** 确定性模板。"
    )
    return (
        summary,
        source_note,
        gallery,
        extraction_note,
        extraction_rows,
        match_rows,
        evidence_rows,
        risk_action,
        explanation,
        phase2_input,
        result,
        "",
        manifest,
    )


def _guard_case_values(case: dict[str, Any]) -> tuple[Any, ...]:
    facts = case["audit_facts"]
    guard = case["guard_result"]
    manifest = case["manifest"]
    extraction_rows = [
        ["输入类型", "synthetic evaluation fixture", "同左", "不是企业真实发票"],
        ["发票号", facts["invoice_number"], facts["invoice_number"], "fixture"],
        ["采购订单号", facts["po_number"], facts["po_number"], "fixture"],
        ["收货单号", "未提供", "LoRA 补出 GRN-20260149", "未知标识符"],
    ]
    match_rows = [
        ["采购订单（PO）", facts["po_number"], "synthetic evaluation fixture"],
        ["收货单（GRN）", "缺失", "规范化审核事实"],
        ["发票", facts["invoice_number"], "synthetic evaluation fixture"],
        ["重复检查", "本案例不展示", "Phase 2 fixture_only"],
    ]
    evidence_rows = [
        ["LoRA 输出", "真实首轮离线 ModelScope 评测 artifact", "不是网页实时推理"],
        ["Guard", "REJECT", "真实 Guard 执行"],
        [
            "关键违规",
            guard["expected_key_violation"],
            "输出补出了输入中不存在的 GRN",
        ],
    ]
    risk_action = (
        "### 风险等级与建议动作\n\n"
        f"**风险等级：** {_risk_label(facts['risk_level'])}  \n"
        f"**建议动作：** {_action_label(facts['recommended_action'])}  \n"
        "风险结论来自既有规范化审核事实，不由 LoRA 决定。"
    )
    explanation = (
        "### Guard 拦截与 fallback\n\n"
        "**Guard 未通过，已自动回退到确定性模板。**  \n"
        "LoRA 输出补出了未知 `GRN-20260149`，并缺少受控输出要求的关键段落；"
        "因此该输出不能成为正式解释。\n\n"
        f"{case['final_explanation']}\n\n"
        "第二轮 LoRA 未通过 hard gate，当前默认正式输出继续使用确定性模板；"
        "Phase 3I 仅作为后续受控评估方向。"
    )
    return (
        "### 案例 C：LoRA 幻觉与 Guard 拦截回退\n\n"
        "这个案例没有发票图片，也不包含 LayoutLMv3 推理。它专门展示解释层"
        "如何阻止模型新增审核事实。",
        "**证据来源：** 输入事实是 synthetic evaluation fixture；"
        "LoRA 文本来自首轮真实离线模型评测 artifact；Guard 为真实执行结果。",
        [],
        "### 解释层事实与模型输出对照\n\n"
        "本案例不是图片抽取案例。下表突出规范事实与 LoRA 新增内容之间的差异。",
        extraction_rows,
        match_rows,
        evidence_rows,
        risk_action,
        explanation,
        facts,
        guard,
        case["lora_raw_output"],
        manifest,
    )


def _risk_label(value: str) -> str:
    return {"low": "低风险", "medium": "中风险", "high": "高风险"}.get(
        value, value
    )


def _action_label(value: str) -> str:
    return {
        "auto_approve": "自动通过",
        "request_human_approval": "转人工审批",
        "reject": "拒绝",
    }.get(value, value)


def _yes_no(value: bool) -> str:
    return "通过" if value else "异常"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
