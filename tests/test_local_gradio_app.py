"""Gradio 页面最小构建测试，不启动服务。"""

import pytest

import demo.app as demo_app
from demo.app import build_app


def _config():
    return build_app().get_config_file()


def test_app_builds_without_launching_or_running_model():
    config = _config()

    assert config["title"] == "ProcureGuard AI"
    assert config["analytics_enabled"] is False
    assert config["space_id"] is None


def test_app_contains_required_inputs_and_buttons():
    components = _config()["components"]
    elem_ids = {
        component.get("props", {}).get("elem_id") for component in components
    }

    assert "demo-case-selector" in elem_ids
    assert "explanation-mode-selector" in elem_ids
    assert "run-audit-button" in elem_ids
    assert "reset-demo-button" in elem_ids


def test_app_contains_explanation_and_audit_outputs():
    components = _config()["components"]
    labels = {component.get("props", {}).get("label") for component in components}

    assert {
        "审核解释",
        "解释来源",
        "原始改写输出",
        "完整审核报告 JSON（AuditReport）",
        "证据",
        "缺失字段",
    } <= labels


def test_missing_gradio_only_blocks_demo_with_install_hint(monkeypatch):
    monkeypatch.setattr(demo_app, "gr", None)

    with pytest.raises(RuntimeError, match=r'\.\[demo\]'):
        demo_app.build_app()
