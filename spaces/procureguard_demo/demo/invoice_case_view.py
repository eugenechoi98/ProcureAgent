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


def preview_values(
    catalog: dict[str, dict[str, Any]], case_id: str
) -> tuple[Any, ...]:
    """返回案例切换时立即展示的六区块内容。"""

    case = catalog[case_id]
    return (
        str((DEMO_ROOT / case["image"]).resolve()),
        case["extraction_rows"],
        case["match_rows"],
        case["evidence_rows"],
        render_risk_action(case),
        render_explanation(case),
        case["recommended_mode"],
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
        f"**证据边界：** {case['scope_note']}"
    )


def render_explanation(
    case: dict[str, Any], result: DemoOutput | None = None
) -> str:
    """展示模板、Guard 和 fallback 状态。"""

    if result is None:
        return (
            "### 6. 审核解释\n"
            "点击“运行审核”后显示确定性模板解释。特定案例会演示受控的 "
            "Guard / fallback 路径；这里不会调用真实 LoRA。"
        )

    guard_state = "通过" if result.guard_passed else "未通过或未启用"
    raw_output = result.raw_rewrite_output or "无"
    fallback = result.fallback_reason or "无"
    return (
        "### 6. 审核解释\n"
        f"{result.explanation_text}\n\n"
        f"**解释来源：** `{result.explanation_source}`  \n"
        f"**Guard：** {guard_state}  \n"
        f"**fallback：** `{fallback}`  \n"
        f"**受控改写原始输出：** {raw_output}\n\n"
        "> 受控改写使用本地 fake provider 演示治理路径，不是真实 LoRA 在线推理；"
        "模板始终是默认正式输出。"
    )
