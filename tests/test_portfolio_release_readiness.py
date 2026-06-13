"""Portfolio release readiness 聚合脚本测试。"""

import json
from pathlib import Path
import subprocess
import sys

from scripts.release.verify_portfolio_release_readiness import verify_release_readiness


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "release" / "verify_portfolio_release_readiness.py"


def test_readiness_reads_deployment_record_without_network() -> None:
    result = verify_release_readiness()

    assert result["ready"] is True
    assert result["scope"] == "local_release_readiness"
    assert result["hf_space_created"] is True
    assert result["hf_space_uploaded"] is True
    assert result["online_deployment_verified"] is False
    assert result["manual_browser_check_required"] is True
    assert result["model_weights_included"] is False
    assert result["gpu_required"] is False
    assert result["api_key_required"] is False
    assert result["network_required_for_runtime"] is False


def test_readiness_aggregates_all_delivery_checks() -> None:
    result = verify_release_readiness()

    assert set(result["checks"]) == {
        "unified_gradio_demo",
        "model_lab_artifacts",
        "hf_space_local_package",
        "langchain_benchmark",
        "docker_delivery",
        "github_actions_ci",
        "documentation",
        "hf_spaces_public_deployment",
    }
    assert all(check["ready"] for check in result["checks"].values())
    assert result["langchain_benchmark_status"] == "ready"
    assert result["ci_config_status"] == "ready"
    assert result["checks"]["hf_spaces_public_deployment"]["online_check_included"] is False


def test_docker_runtime_is_not_claimed_without_cli() -> None:
    result = verify_release_readiness()

    if not result["checks"]["docker_delivery"]["docker_cli_available"]:
        assert result["docker_runtime_status"] == "runtime_not_verified"
        assert "docker_runtime_not_verified_in_current_environment" in result["warnings"]


def test_cli_prints_json_without_default_write(tmp_path: Path) -> None:
    before = set(tmp_path.rglob("*"))
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["ready"] is True
    assert set(tmp_path.rglob("*")) == before


def test_explicit_output_writes_same_json(tmp_path: Path) -> None:
    output = tmp_path / "release" / "readiness.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(completed.stdout)
