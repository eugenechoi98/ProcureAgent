"""本地离线 Demo readiness 脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.demo.verify_demo_readiness import (
    DEFAULT_FIXTURE,
    verify_demo_readiness,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "demo" / "verify_demo_readiness.py"


def _cases() -> list[dict]:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, cases: list[dict]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_default_run_is_read_only_and_structured(tmp_path):
    before = set(tmp_path.iterdir())

    completed = _run()
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["ready"] is True
    assert payload["case_count"] == 13
    assert payload["readiness_scope"] == "local_offline_demo_only"
    assert payload["errors"] == []
    assert set(tmp_path.iterdir()) == before


def test_missing_fixture_fails(tmp_path):
    result = verify_demo_readiness(tmp_path / "missing.json")

    assert result["ready"] is False
    assert result["fixture_exists"] is False
    assert "fixture_missing" in result["errors"]


def test_duplicate_case_id_fails(tmp_path):
    cases = _cases()
    cases[1]["case_id"] = cases[0]["case_id"]

    result = verify_demo_readiness(_write_fixture(tmp_path, cases))

    assert result["ready"] is False
    assert result["unique_case_ids"] is False
    assert any(error.startswith("duplicate_case_id:") for error in result["errors"])


def test_missing_required_field_fails(tmp_path):
    cases = _cases()
    del cases[0]["facts"]["risk_level"]

    result = verify_demo_readiness(_write_fixture(tmp_path, cases))

    assert result["ready"] is False
    assert any("missing_field:risk_level" in error for error in result["errors"])


def test_missing_core_scenario_fails(tmp_path):
    cases = [
        case
        for case in _cases()
        if case["case_id"] != "experimental_guard_fail"
    ]
    cases.append({**cases[0], "case_id": "replacement_case"})

    result = verify_demo_readiness(_write_fixture(tmp_path, cases))

    assert result["ready"] is False
    assert (
        "missing_required_case:experimental_guard_fail" in result["errors"]
    )


def test_json_output_shape_is_stable():
    result = verify_demo_readiness()

    assert set(result) == {
        "ready",
        "readiness_scope",
        "fixture_path",
        "fixture_exists",
        "case_count",
        "expected_case_count",
        "unique_case_ids",
        "required_cases",
        "requirements",
        "checks",
        "errors",
    }
    assert set(result["requirements"]) == {
        "api_key_required",
        "network_required",
        "gpu_required",
        "qwen_required",
        "lora_required",
        "service_start_required",
    }


def test_default_cli_does_not_write_file(tmp_path):
    output = tmp_path / "readiness.json"

    completed = _run()

    assert completed.returncode == 0
    assert output.exists() is False


def test_explicit_output_writes_same_json(tmp_path):
    output = tmp_path / "reports" / "readiness.json"

    completed = _run("--output", str(output))

    assert completed.returncode == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        completed.stdout
    )


def test_no_api_key_gpu_or_model_environment_is_required(monkeypatch):
    for name in (
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "OPENAI_API_KEY",
        "CUDA_VISIBLE_DEVICES",
        "PHASE3_MODEL_DIR",
        "PHASE3_ADAPTER_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    result = verify_demo_readiness()

    assert result["ready"] is True
    assert all(value is False for value in result["requirements"].values())


def test_readiness_does_not_modify_artifacts():
    artifacts = PROJECT_ROOT / "artifacts"
    before = (
        artifacts.exists(),
        artifacts.stat().st_mtime_ns if artifacts.exists() else None,
    )

    result = verify_demo_readiness()

    after = (
        artifacts.exists(),
        artifacts.stat().st_mtime_ns if artifacts.exists() else None,
    )
    assert result["ready"] is True
    assert after == before
