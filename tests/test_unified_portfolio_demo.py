"""统一 Portfolio Demo 的离线构建和展示口径测试。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from demo.app import build_app
from demo.architecture_view import ARCHITECTURE_MARKDOWN
from demo.model_lab_view import (
    layout_metric_rows,
    load_model_lab_artifacts,
    lora_guard_case_rows,
    lora_guard_visual_case,
    render_lora_fallback,
    render_lora_guard_result,
    render_lora_raw_output,
    render_lora_summary,
    render_model_lab_summary,
)
from scripts.demo.run_unified_portfolio_demo_smoke import run_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "demo" / "run_unified_portfolio_demo_smoke.py"


def _config() -> dict:
    return build_app().get_config_file()


def _components() -> list[dict]:
    return _config()["components"]


def _component_props(elem_id: str) -> dict:
    for component in _components():
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props
    raise AssertionError(f"Missing component elem_id={elem_id}")


def _labels() -> set[str]:
    return {
        component.get("props", {}).get("label")
        for component in _components()
        if component.get("props", {}).get("label") is not None
    }


def test_app_builds_with_current_tabs() -> None:
    config = _config()
    tab_labels = [
        component.get("props", {}).get("label")
        for component in config["components"]
        if component.get("type") == "tabitem"
    ]

    assert config["title"] == "ProcureGuard AI"
    assert config["analytics_enabled"] is False
    assert [
        "产品总览",
        "Scenario Demo",
        "完整流程视频",
        "GitHub / 运行边界",
    ] == tab_labels


def test_main_chain_case_validation_and_explanation_controls_are_visible() -> None:
    labels = _labels()

    assert _component_props("demo-case-selector")["value"] == "normal_invoice"
    assert _component_props("case-explanation-mode-selector")["value"] == "LoRA OFF"
    case_values = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in _component_props("demo-case-selector")["choices"]
    }
    mode_values = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in _component_props("case-explanation-mode-selector")["choices"]
    }
    assert case_values == {
        "normal_invoice",
        "missing_goods_receipt",
        "missing_po_number",
        "vendor_name_mismatch",
        "duplicate_invoice",
    }
    assert mode_values == {"LoRA OFF", "LoRA ON"}
    assert {
        "选择案例",
        "1. 发票图片",
        "2. OCR / LayoutLMv3 字段识别 + 人工确认",
        "风险等级",
        "建议动作",
        "AuditReport JSON",
        "Trace",
    } <= labels


def test_public_demo_contains_chinese_usage_guidance() -> None:
    markdown_values = [
        component.get("props", {}).get("value", "")
        for component in _components()
        if component.get("type") == "markdown"
    ]
    rendered = "\n".join(str(value) for value in markdown_values)

    assert "受控采购发票审核 Agent" in rendered
    assert "公网 Space 使用稳定的 scenario-driven demo" in rendered
    assert "视频为静态浏览器播放资源" in json.dumps(
        _config(), ensure_ascii=False
    )
    assert "LoRA OFF/ON 只切换解释文本" in rendered
    assert "`risk_level` 和 `recommended_action` 始终由规则生成" in rendered


def test_public_demo_avoids_bare_english_business_labels() -> None:
    config_text = json.dumps(_config(), ensure_ascii=False)

    for forbidden in (
        '"Invoice Audit"',
        '"Audit Trail"',
        '"Canonical Facts"',
        '"Deterministic Template"',
        '"Optional Controlled Rewrite"',
        '"Risk Engine"',
        '"Three-Way Match"',
    ):
        assert forbidden not in config_text


def test_model_lab_loads_artifacts_and_displays_required_scope() -> None:
    artifacts = load_model_lab_artifacts()
    summary = render_model_lab_summary(artifacts)
    rows = dict(layout_metric_rows(artifacts))

    assert artifacts["manifest"]["offline_only"] is True
    assert rows["official_test"] == "false"
    assert "OCR + Regex baseline Macro F1" in summary
    assert "修复后 LayoutLMv3 Macro F1" in summary
    assert "日期字段 F1" in summary
    assert "0.8067" in summary
    assert "0.1423" in summary
    assert "0.8764" in summary
    assert "不是当前网页实时模型推理" not in summary
    assert "当前网页不会加载" not in summary
    assert "缺失 artifacts" not in summary


def test_model_lab_lora_scope_and_manifest_evidence_are_preserved() -> None:
    artifacts = load_model_lab_artifacts()
    summary = render_lora_summary(artifacts)
    guard_sources = {row[1] for row in lora_guard_case_rows(artifacts)}
    missing = {
        item["artifact"] for item in artifacts["manifest"]["missing_artifacts"]
    }

    assert "第二轮 Adapter 是否通过 hard gate：`false`" in summary
    assert "没有作为默认解释器上线" in summary
    assert "确定性模板 + 可选受控改写 + 输出守卫 + 模板回退" in summary
    assert "real_offline_model_output" in guard_sources
    assert "test_fixture" in guard_sources
    assert "first_lora_training_curve" in missing
    assert "second_lora_local_checkpoint_adapter_predictions_runtime_copy" in missing
    assert "public_receipt_images_for_selected_predictions" in missing


def test_model_lab_surfaces_real_lora_guard_fallback_evidence() -> None:
    artifacts = load_model_lab_artifacts()
    case = lora_guard_visual_case(artifacts)

    assert case["source_type"] == "real_offline_model_output"
    assert case["rewrite_output"] == (
        "Generated explanation included unsupported GRN-20260149."
    )
    assert "REJECT" in render_lora_guard_result(case)
    assert "unknown_identifier:GRN-20260149" in render_lora_guard_result(case)
    assert "未补全未知 GRN" in render_lora_fallback(case)
    assert "request_human_approval" in render_lora_fallback(case)
    assert "real_offline_model_output" in render_lora_raw_output(case)

    assert "GRN-20260149" in render_lora_guard_result(case)


def test_model_lab_artifacts_remain_available_but_not_as_main_tab() -> None:
    components = _components()
    tab_labels = [
        component.get("props", {}).get("label")
        for component in components
        if component.get("type") == "tabitem"
    ]
    labels = _labels()

    assert "Model Lab" not in tab_labels
    assert "模型实验 manifest JSON" not in labels
    assert load_model_lab_artifacts()["manifest"]["offline_only"] is True


def test_unified_build_requires_no_model_network_gpu_or_api_key(monkeypatch) -> None:
    for name in (
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "OPENAI_API_KEY",
        "CUDA_VISIBLE_DEVICES",
        "PHASE3_MODEL_DIR",
        "PHASE3_ADAPTER_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    result = run_smoke()

    assert result["ready"] is True
    assert result["requirements"] == {
        "api_key_required": False,
        "network_required": False,
        "gpu_required": False,
        "layoutlmv3_required": False,
        "qwen_required": False,
        "real_lora_required": False,
        "long_running_service_started": False,
        "browser_opened": False,
    }


def test_architecture_tab_contains_governance_explanations() -> None:
    text = ARCHITECTURE_MARKDOWN

    for node in (
        "受控采购审核 Agent",
        "autonomous LLM",
        "发票图片",
        "OCR + LayoutLMv3 字段抽取",
        "Agent 工具",
        "三单匹配",
        "Policy RAG",
        "风险规则引擎",
        "规范化审核事实",
        "确定性模板",
        "受控 rewrite",
        "Guard",
        "fallback",
        "审计轨迹",
        "审核报告",
    ):
        assert node in text
    assert "模型不能直接决定风险等级" in text
    assert "LoRA 不能修改建议动作" in text
    assert "模板回退保证" in text
    assert "审计轨迹" in text
    assert "受控采购审核 Agent" in text
    assert "不是让大模型直接决定风险" in text


def test_smoke_cli_prints_json_without_writing(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["ready"] is True
    assert payload["tabs"] == [
        "产品总览",
        "Scenario Demo",
        "完整流程视频",
        "GitHub / 运行边界",
    ]
    assert payload["default_case"] == "normal_invoice"
    assert payload["default_mode"] == "LoRA OFF"
    assert set(tmp_path.iterdir()) == before


def test_smoke_cli_explicit_output_writes_same_json(tmp_path: Path) -> None:
    output = tmp_path / "smoke" / "unified.json"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--output", str(output)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        completed.stdout
    )
