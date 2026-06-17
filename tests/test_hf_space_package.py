"""Hugging Face Spaces 最小发布包离线校验。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.demo.build_hf_space_package import SPACE_ROOT, build_package
from scripts.demo.run_hf_space_package_smoke import run_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _space_files() -> list[Path]:
    return [path for path in SPACE_ROOT.rglob("*") if path.is_file()]


def test_space_package_exists_with_required_files() -> None:
    result = build_package()

    assert result["ready"] is True
    assert SPACE_ROOT.exists()
    assert (SPACE_ROOT / "README.md").exists()
    assert (SPACE_ROOT / "app.py").exists()
    assert (SPACE_ROOT / "requirements.txt").exists()


def test_readme_contains_hf_spaces_yaml() -> None:
    build_package()
    readme = (SPACE_ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.startswith("---\n")
    assert "sdk: gradio" in readme
    assert "sdk_version: 5.50.0" in readme
    assert "app_file: app.py" in readme
    assert "不加载 LayoutLMv3" in readme
    assert "Path A 手动审核" in readme
    assert "5 个案例都有发票图片、Run Audit 按钮和结果卡片" in readme
    assert "每张发票图片绑定唯一 scenario_id" in readme
    assert "页面不调用 OCR 模型、不调用 LayoutLMv3" in readme
    assert "不展示空字段或失败状态" in readme
    assert "LoRA OFF/ON 切换放在 Audit Result 内部" in readme


def test_requirements_are_minimal_and_pinned() -> None:
    build_package()
    requirements = (SPACE_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "gradio==5.50.0" in requirements
    assert "torch" not in requirements.lower()
    assert "transformers" not in requirements.lower()
    assert "peft" not in requirements.lower()
    assert "bitsandbytes" not in requirements.lower()


def test_package_excludes_forbidden_assets() -> None:
    result = build_package()
    files = [path.relative_to(SPACE_ROOT).as_posix() for path in _space_files()]
    rendered = "\n".join(files).lower()

    assert result["contains_model_weights"] is False
    assert result["contains_database"] is False
    assert result["contains_notebook"] is False
    assert result["forbidden_hits"] == []
    assert ".venv" not in rendered
    assert "adapter" not in rendered
    assert "requirements/phase3-lora.txt" not in rendered
    assert not any(path.endswith(".ipynb") for path in files)
    assert not any(path.endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt")) for path in files)
    assert not any(path.endswith((".sqlite", ".sqlite3", ".db")) for path in files)


def test_package_can_import_and_build_gradio_app() -> None:
    build_package()
    result = run_smoke()

    assert result["ready"] is True
    assert result["tabs"] == ["Path A 手动审核", "Path B Scenario Demo", "系统说明"]
    assert result["default_case"] == "normal_invoice"
    assert result["default_mode"] == "LoRA OFF"
    assert result["invoice_cases"]["count"] == 5
    assert result["invoice_cases"]["images_present"] is True
    assert result["e2e_cases"]["count"] == 3
    assert result["e2e_cases"]["evidence_present"] is True
    assert result["model_lab"]["manifest_loaded"] is True
    assert result["model_lab"]["layoutlmv3_metrics_loaded"] is True
    assert result["model_lab"]["lora_metrics_loaded"] is True


def test_package_requires_no_network_model_gpu_or_api_key(monkeypatch) -> None:
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


def test_build_script_is_repeatable_and_prints_json() -> None:
    first = build_package()
    second = build_package()

    assert first["ready"] is True
    assert second["ready"] is True
    assert first["copied_files"] == second["copied_files"]

    completed = subprocess.run(
        [sys.executable, "scripts/demo/build_hf_space_package.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["ready"] is True


def test_smoke_script_outputs_ready_json() -> None:
    build_package()
    completed = subprocess.run(
        [sys.executable, "scripts/demo/run_hf_space_package_smoke.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["ready"] is True
