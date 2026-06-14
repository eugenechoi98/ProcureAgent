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
        from demo.e2e_case_view import load_e2e_case_catalog
        from demo.invoice_case_view import load_invoice_case_catalog
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
        case_catalog = load_invoice_case_catalog()
        e2e_catalog = load_e2e_case_catalog()
        e2e_default_case = _component_value(components, "e2e-case-selector")
        default_case = _component_value(components, "demo-case-selector")
        default_mode = _component_value(components, "explanation-mode-selector")
    except Exception as exc:  # pragma: no cover - returned in smoke JSON
        tabs = []
        artifacts = {}
        case_catalog = {}
        e2e_catalog = {}
        e2e_default_case = None
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
    if len(case_catalog) != 5:
        errors.append("invoice_case_count_not_five")
    if len(e2e_catalog) != 3:
        errors.append("e2e_case_count_not_three")
    if e2e_default_case != "case_a_standard_pass":
        errors.append("e2e_default_case_mismatch")
    if not all(
        (SPACE_ROOT / "demo" / case["image"]).is_file()
        for case in case_catalog.values()
    ):
        errors.append("invoice_case_image_missing")
    if not all(
        (
            SPACE_ROOT
            / "demo"
            / "e2e_cases"
            / case_id
            / "manifest.json"
        ).is_file()
        for case_id in e2e_catalog
    ):
        errors.append("e2e_case_evidence_missing")

    return {
        "ready": not errors,
        "scope": "hf_space_package_offline_build",
        "space_root": str(SPACE_ROOT),
        "tabs": tabs,
        "default_case": default_case,
        "default_mode": default_mode,
        "invoice_cases": {
            "count": len(case_catalog),
            "case_ids": list(case_catalog),
            "images_present": not any(
                error == "invoice_case_image_missing" for error in errors
            ),
        },
        "e2e_cases": {
            "count": len(e2e_catalog),
            "case_ids": list(e2e_catalog),
            "default_case": e2e_default_case,
            "evidence_present": not any(
                error == "e2e_case_evidence_missing" for error in errors
            ),
        },
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
