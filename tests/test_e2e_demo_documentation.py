"""端到端证据链文档口径测试。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_readme_explains_e2e_evidence_and_runtime_boundaries() -> None:
    text = _read("README.md")

    for phrase in (
        "不支持上传任意发票并现场运行 LayoutLMv3",
        "真实 SROIE validation 图片",
        "PO/GRN 是 mock 采购上下文",
        "真实离线 LoRA artifact",
        "单个网页案例不用于证明整体指标",
    ):
        assert phrase in text


def test_walkthrough_contains_interview_script_and_required_faq() -> None:
    text = _read("docs/DEMO_WALKTHROUGH.md")

    for phrase in (
        "3–5 分钟面试演示脚本",
        "这个网页能不能上传任意发票现场识别",
        "右边字段是不是预设的",
        "为什么不把 LoRA 直接上线",
        "这是 Agent 还是规则系统",
        "mock PO/GRN 会不会让项目不真实",
        "unknown_identifier:GRN-20260149",
    ):
        assert phrase in text


def test_design_and_deployment_keep_offline_claims_honest() -> None:
    text = "\n".join(
        (
            _read("docs/PORTFOLIO_DEMO_DESIGN.md"),
            _read("docs/HF_SPACES_DEPLOYMENT.md"),
        )
    )

    for phrase in (
        "LayoutLMv3 offline checkpoint prediction",
        "mock procurement context",
        "does not accept arbitrary invoice uploads",
        "当前页面不支持任意发票上传和在线模型推理",
        "不包含模型权重",
    ):
        assert phrase in text
