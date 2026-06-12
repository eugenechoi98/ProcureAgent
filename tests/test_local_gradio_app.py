"""Gradio 页面最小构建测试，不启动服务。"""

import warnings

from demo.app import build_app


def _config():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Setting 'api_name=False'.*",
            category=DeprecationWarning,
        )
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
        "Explanation Text",
        "Explanation Source",
        "Raw Rewrite Output",
        "Complete AuditReport JSON",
        "Evidence",
        "Missing Fields",
    } <= labels
