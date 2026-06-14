"""离线验证 Hugging Face Spaces 本地发布包。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPACE_ROOT = PROJECT_ROOT / "spaces" / "procureguard_demo"


def run_smoke() -> dict[str, Any]:
    """从发布包目录独立 import 并构建 Gradio App。"""

    errors: list[str] = []
    original_path = list(sys.path)
    original_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path = [str(SPACE_ROOT), *[item for item in sys.path if item != str(PROJECT_ROOT)]]
    try:
        from demo.app import build_app
        from demo.model_lab_view import load_model_lab_artifacts

        app = build_app()
        config = app.get_config_file()
        components = config["components"]
        tabs = [
            item.get("props", {}).get("label")
            for item in components
            if item.get("type") == "tabitem"
        ]
        artifacts = load_model_lab_artifacts()
        default_case = _component_value(components, "demo-case-selector")
        default_mode = _component_value(components, "explanation-mode-selector")
    except Exception as exc:  # pragma: no cover - returned in smoke JSON
        tabs = []
        artifacts = {}
        default_case = None
        default_mode = None
        errors.append(f"{exc.__class__.__name__}: {exc}")
    finally:
        sys.path = original_path
        sys.dont_write_bytecode = original_dont_write_bytecode

    for expected in ("发票审核", "模型实验", "系统架构"):
        if expected not in tabs:
            errors.append(f"missing_tab:{expected}")
    if default_case != "normal_invoice":
        errors.append("default_case_not_normal_invoice")
    if default_mode != "template":
        errors.append("default_mode_not_template")

    return {
        "ready": not errors,
        "scope": "hf_space_package_offline_build",
        "space_root": str(SPACE_ROOT),
        "tabs": tabs,
        "default_case": default_case,
        "default_mode": default_mode,
        "model_lab": {
            "manifest_loaded": bool(artifacts.get("manifest")),
            "layoutlmv3_metrics_loaded": bool(artifacts.get("layout_metrics")),
            "lora_metrics_loaded": bool(artifacts.get("lora_metrics")),
        },
        "requirements": {
            "api_key_required": False,
            "network_required": False,
            "gpu_required": False,
            "layoutlmv3_required": False,
            "qwen_required": False,
            "real_lora_required": False,
            "long_running_service_started": False,
            "browser_opened": False,
        },
        "errors": errors,
    }


def _component_value(components: list[dict[str, Any]], elem_id: str) -> Any:
    for component in components:
        props = component.get("props", {})
        if props.get("elem_id") == elem_id:
            return props.get("value")
    return None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run_smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
