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


def test_app_builds_with_three_tabs() -> None:
    config = _config()
    tab_labels = [
        component.get("props", {}).get("label")
        for component in config["components"]
        if component.get("type") == "tabitem"
    ]

    assert config["title"] == "ProcureGuard AI"
    assert config["analytics_enabled"] is False
    assert ["Invoice Audit", "Model Lab", "Architecture"] == tab_labels


def test_invoice_audit_keeps_existing_inputs_outputs_and_defaults() -> None:
    labels = _labels()

    assert _component_props("demo-case-selector")["value"] == "normal_invoice"
    assert _component_props("explanation-mode-selector")["value"] == "template"
    case_values = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in _component_props("demo-case-selector")["choices"]
    }
    mode_values = {
        choice[1] if isinstance(choice, (list, tuple)) else choice
        for choice in _component_props("explanation-mode-selector")["choices"]
    }
    assert "normal_invoice" in case_values
    assert "template" in mode_values
    assert {
        "Demo Case",
        "Explanation Mode",
        "Risk Level",
        "Recommended Action",
        "Anomaly Types",
        "Evidence",
        "Missing Fields",
        "Explanation Text",
        "Explanation Source",
        "Used Rewrite",
        "Guard Passed",
        "Fallback Reason",
        "Facts Hash",
        "Template Version",
        "Prompt Version",
        "Model Version",
        "Adapter Version",
        "Raw Rewrite Output",
        "Safe Fallback Detail",
        "Complete AuditReport JSON",
    } <= labels


def test_model_lab_loads_artifacts_and_displays_required_scope() -> None:
    artifacts = load_model_lab_artifacts()
    summary = render_model_lab_summary(artifacts)
    rows = dict(layout_metric_rows(artifacts))

    assert artifacts["manifest"]["offline_only"] is True
    assert rows["official_test"] == "false"
    assert "official_test=false" in summary
    assert "offline_checkpoint_inference" in summary
    assert "local_validation_split_seed_42" in summary
    assert "0.8067" in summary
    assert "0.1423" in summary
    assert "0.8764" in summary
    assert "field-level JSON only" in summary


def test_model_lab_lora_scope_and_missing_artifacts_are_visible() -> None:
    artifacts = load_model_lab_artifacts()
    summary = render_lora_summary(artifacts)
    guard_sources = {row[1] for row in lora_guard_case_rows(artifacts)}
    missing = {
        item["artifact"] for item in artifacts["manifest"]["missing_artifacts"]
    }

    assert "Second adapter hard gate passed: `false`" in summary
    assert "第二轮 adapter 未通过 hard gate" in summary
    assert "第三次训练暂停" in summary
    assert "LoRA 不作为默认审核解释器" in summary
    assert "真实 LoRA 当前没有在网页运行" in summary
    assert "real_offline_model_output" in guard_sources
    assert "test_fixture" in guard_sources
    assert "first_lora_training_curve" in missing
    assert "second_lora_local_checkpoint_adapter_predictions_runtime_copy" in missing
    assert "public_receipt_images_for_selected_predictions" in missing


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
        "Invoice",
        "OCR + LayoutLMv3",
        "Agent Tools",
        "Three-Way Match",
        "Policy RAG",
        "Risk Engine",
        "Canonical Facts",
        "Deterministic Template",
        "Optional Controlled Rewrite",
        "Guard",
        "Fallback",
        "Audit Trail",
        "AuditReport",
    ):
        assert node in text
    assert "模型不能直接决定 risk" in text
    assert "LoRA 不能改变 `recommended_action`" in text
    assert "Fallback 保证" in text
    assert "Audit Trail" in text
    assert "第三次训练暂停" in text


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
    assert payload["tabs"] == ["Invoice Audit", "Model Lab", "Architecture"]
    assert payload["default_case"] == "normal_invoice"
    assert payload["default_mode"] == "template"
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
