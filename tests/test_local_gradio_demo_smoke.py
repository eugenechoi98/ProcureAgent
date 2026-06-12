"""本地 Demo smoke 脚本测试。"""

import json
from pathlib import Path
import subprocess
import sys

from scripts.demo.run_local_demo_smoke import run_smoke

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "demo" / "run_local_demo_smoke.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_smoke_runs_all_cases_and_modes():
    result = run_smoke()

    assert result["ready"] is True
    assert result["case_count"] == 13
    assert len(result["cases"]) == 13
    assert {
        "shadow",
        "experimental_guard_pass",
        "experimental_guard_fail",
        "provider_runtime_error",
        "invalid_output",
        "high_risk_template_fallback",
    } <= result["mode_checks"].keys()


def test_smoke_json_shape_is_stable():
    result = run_smoke()

    assert set(result) == {
        "ready",
        "scope",
        "case_count",
        "cases",
        "mode_checks",
        "requirements",
        "errors",
    }
    assert result["scope"] == "local_offline_gradio_service"
    assert all(value is False for value in result["requirements"].values())


def test_default_cli_prints_json_without_writing(tmp_path):
    before = set(tmp_path.iterdir())

    completed = _run()
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["ready"] is True
    assert set(tmp_path.iterdir()) == before


def test_explicit_output_writes_same_json(tmp_path):
    output = tmp_path / "smoke" / "result.json"

    completed = _run("--output", str(output))

    assert completed.returncode == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        completed.stdout
    )


def test_smoke_requires_no_environment(monkeypatch):
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
    assert all(value is False for value in result["requirements"].values())


def test_smoke_does_not_modify_artifacts():
    artifacts = PROJECT_ROOT / "artifacts"
    before = (
        artifacts.exists(),
        artifacts.stat().st_mtime_ns if artifacts.exists() else None,
    )

    result = run_smoke()

    after = (
        artifacts.exists(),
        artifacts.stat().st_mtime_ns if artifacts.exists() else None,
    )
    assert result["ready"] is True
    assert after == before
