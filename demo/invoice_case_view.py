"""加载发票案例展示元数据，并生成 Gradio 展示值。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from demo.demo_service import DemoOutput


DEMO_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = DEMO_ROOT / "invoice_cases.json"

RISK_LABELS = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
}
ACTION_LABELS = {
    "auto_approve": "自动通过",
    "request_human_approval": "转人工审批",
    "reject": "拒绝",
}
EXPLANATION_MODE_LABELS = {
    "template": "确定性模板",
    "shadow": "Shadow 影子改写",
    "experimental_guard_pass": "实验改写：Guard 通过",
    "experimental_guard_fail": "实验改写：Guard 拦截回退",
    "provider_runtime_error": "Provider 运行错误回退",
    "invalid_output": "非法输出回退",
}


def load_invoice_case_catalog(path: Path = CATALOG_PATH) -> dict[str, dict[str, Any]]:
    """读取案例目录，并校验案例编号和图片文件。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = {item["case_id"]: item for item in payload}
    if len(catalog) != len(payload):
        raise ValueError("发票案例目录包含重复 case_id。")
    for case in payload:
        image_path = DEMO_ROOT / case["image"]
        if not image_path.is_file():
            raise FileNotFoundError(f"发票案例图片不存在：{image_path}")
    return catalog


def case_choices(catalog: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    """返回带中文标题的稳定下拉选项。"""

    return [(case["display_name"], case_id) for case_id, case in catalog.items()]


def explanation_mode_choices(modes: list[str]) -> list[tuple[str, str]]:
    """返回中文展示标签，并保留稳定的内部模式值。"""

    return [(EXPLANATION_MODE_LABELS[mode], mode) for mode in modes]


def preview_values(
    catalog: dict[str, dict[str, Any]], case_id: str
) -> tuple[Any, ...]:
    """返回案例切换时立即展示的六区块内容。"""

    case = catalog[case_id]
    return (
        render_case_summary(case),
        render_image_note(case),
        str((DEMO_ROOT / case["image"]).resolve()),
        case["extraction_rows"],
        pending_match_rows(),
        pending_evidence_rows(),
        render_pending_risk_action(case),
        render_pending_explanation(case),
        case["recommended_mode"],
    )


def pending_match_rows() -> list[list[str]]:
    """运行前不预填三单匹配结论。"""

    return [["审核状态", "尚未运行", "点击“运行审核”后生成"]]


def pending_evidence_rows() -> list[list[str]]:
    """运行前不预填政策和规则证据。"""

    return [["审核状态", "尚未运行", "点击“运行审核”后生成"]]


def render_pending_risk_action(case: dict[str, Any]) -> str:
    """区分案例预期与尚未生成的正式审核结果。"""

    return (
        "### 5. 建议动作 + 风险等级\n"
        "**审核结果：** 尚未运行  \n"
        f"**案例预期：** {RISK_LABELS.get(case['risk_level'], case['risk_level'])} / "
        f"{ACTION_LABELS.get(case['recommended_action'], case['recommended_action'])}  \n"
        "点击“运行审核”后生成本次审核的风险等级和建议动作。"
    )


def render_pending_explanation(case: dict[str, Any]) -> str:
    """运行前仅说明解释路径，不展示正式解释。"""

    return (
        "### 6. 审核解释\n"
        "**正式解释：** 尚未运行  \n"
        f"**本案例将展示：** {_case_governance_note(case['recommended_mode'])}  \n"
        "点击“运行审核”后生成正式解释；技术版本和原始输出仍收在折叠区。"
    )


def render_case_summary(case: dict[str, Any]) -> str:
    """渲染案例摘要卡片。"""

    governance_note = _case_governance_note(case["recommended_mode"])
    return (
        "### 当前案例\n"
        f"**{case['display_name']}**  \n"
        f"{case['summary']}  \n"
        f"预期风险：**{RISK_LABELS.get(case['risk_level'], case['risk_level'])}**；"
        f"建议动作：**{ACTION_LABELS.get(case['recommended_action'], case['recommended_action'])}**。  \n"
        f"**解释路径：** {governance_note}"
    )


def render_pending_status(case: dict[str, Any]) -> str:
    """案例切换后在操作区提示下一步。"""

    return (
        "### 审核状态：待运行\n"
        f"当前案例：**{case['display_name']}**。点击“运行审核”查看正式结果。"
    )


def render_completed_status(case: dict[str, Any], result: DemoOutput) -> str:
    """审核完成后在按钮附近显示最关键的结果。"""

    return (
        "### 审核状态：已完成\n"
        f"**当前案例：** {case['display_name']}  \n"
        f"**风险等级：** {RISK_LABELS.get(result.risk_level, result.risk_level)}  \n"
        f"**建议动作：** {ACTION_LABELS.get(result.recommended_action, result.recommended_action)}  \n"
        f"**解释来源：** {_explanation_source_label(result)}"
    )


def render_image_note(case: dict[str, Any]) -> str:
    """渲染轻量图片说明。"""

    return (
        "#### 1. 发票示意图\n"
        f"演示用合成示意图。{case['source_note']}；用于演示案例流程，"
        "不代表单图模型评测结论。"
    )


def render_risk_action(
    case: dict[str, Any], result: DemoOutput | None = None
) -> str:
    """展示风险等级与建议动作，运行后以审核结果为准。"""

    risk_level = result.risk_level if result else case["risk_level"]
    action = result.recommended_action if result else case["recommended_action"]
    state = "审核结果" if result else "案例预期"
    return (
        f"### 5. 建议动作 + 风险等级\n"
        f"**{state}：** {RISK_LABELS.get(risk_level, risk_level)}  \n"
        f"**建议动作：** {ACTION_LABELS.get(action, action)}  \n"
        "**说明：** 这是案例级演示结果，整体模型指标请见“模型实验”页。"
    )


def render_explanation(
    case: dict[str, Any], result: DemoOutput | None = None
) -> str:
    """展示模板、Guard 和 fallback 状态。"""

    if result is None:
        return (
            "### 6. 审核解释\n"
            "点击“运行审核”后先显示最终正式解释。特定案例会出现简短的 "
            "Guard / fallback 摘要；详细版本号和原始输出收在下方折叠区。"
        )

    fallback = result.fallback_reason or "无"
    governance_note = _governance_note(result)
    return (
        "### 6. 审核解释\n"
        f"{result.explanation_text}\n\n"
        f"**解释来源：** `{result.explanation_source}`  \n"
        f"**治理摘要：** {governance_note}  \n"
        f"**fallback：** `{fallback}`"
    )


def _governance_note(result: DemoOutput) -> str:
    """生成面向展示的 Guard/fallback 摘要。"""

    if result.fallback_reason == "guard_failed":
        return "Guard 未通过，已自动回退到确定性模板。"
    if result.fallback_reason == "high_risk_template_only":
        return "高风险场景默认使用确定性模板解释。"
    if result.fallback_reason and result.fallback_reason != "mvp_template_default":
        return "已使用 fallback，正式输出仍来自确定性模板。"
    if result.used_rewrite and result.guard_passed:
        return "受控 rewrite 已通过 Guard，但不会改变风险等级或建议动作。"
    return "模板解释为当前正式输出。"


def _case_governance_note(mode: str) -> str:
    """说明案例预设会展示的解释治理路径。"""

    if mode == "experimental_guard_fail":
        return "会展示 Guard 拦截并自动回退到确定性模板。"
    if mode == "template":
        return "使用确定性模板；高风险案例不会尝试自由改写。"
    if mode == "shadow":
        return "影子改写仅用于对比，正式输出仍使用确定性模板。"
    return "会展示受控改写及必要的 fallback。"


def _explanation_source_label(result: DemoOutput) -> str:
    """把技术来源转换为面向演示的中文说明。"""

    if result.fallback_reason == "guard_failed":
        return "Guard 拦截后回退到确定性模板"
    if result.fallback_reason == "high_risk_template_only":
        return "高风险确定性模板"
    if result.fallback_reason and result.fallback_reason != "mvp_template_default":
        return "fallback 后确定性模板"
    if result.used_rewrite and result.guard_passed:
        return "Guard 通过的受控改写"
    return "确定性模板"
