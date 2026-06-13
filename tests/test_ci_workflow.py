"""GitHub Actions CPU-only workflow 静态测试。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_uses_cpu_python_and_pinned_actions() -> None:
    workflow = _workflow_text()

    assert "runs-on: ubuntu-latest" in workflow
    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'python -m pip install -e ".[demo,langchain,test]"' in workflow


def test_workflow_runs_delivery_and_full_validation() -> None:
    workflow = _workflow_text()

    for command in (
        "python -m pip check",
        "python scripts/demo/verify_model_lab_artifacts.py",
        "python scripts/demo/run_unified_portfolio_demo_smoke.py",
        "python scripts/demo/build_hf_space_package.py",
        "python scripts/demo/run_hf_space_package_smoke.py",
        "tests/test_langchain_policy_demo.py tests/test_langchain_policy_benchmark.py",
        "tests/test_docker_delivery_config.py",
        "python scripts/release/verify_portfolio_release_readiness.py",
        "python -m pytest tests -q",
    ):
        assert command in workflow


def test_workflow_has_no_secret_model_or_gpu_configuration() -> None:
    workflow = _workflow_text().lower()

    for forbidden in (
        "secrets.",
        "hf_token",
        "huggingface_token",
        "openai_api_key",
        "cuda",
        "nvidia",
        "phase3_model_dir",
        "phase3_adapter_dir",
    ):
        assert forbidden not in workflow


def test_workflow_has_read_only_repository_permission() -> None:
    workflow = _workflow_text()

    assert "permissions:\n  contents: read" in workflow
    assert "timeout-minutes: 20" in workflow
