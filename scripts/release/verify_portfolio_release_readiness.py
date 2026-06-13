"""聚合验证 ProcureGuard AI 本地作品集发布准备状态。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.demo.run_unified_portfolio_demo_smoke import run_smoke as run_unified_smoke


def verify_release_readiness() -> dict[str, Any]:
    """只读聚合本地交付证据，不执行在线部署。"""

    warnings: list[str] = []
    blockers: list[str] = []
    checks: dict[str, dict[str, Any]] = {}

    unified = run_unified_smoke()
    checks["unified_gradio_demo"] = {
        "ready": unified["ready"],
        "tabs": unified["tabs"],
        "errors": unified["errors"],
    }

    model_lab = _check_model_lab()
    checks["model_lab_artifacts"] = model_lab

    hf_package = _run_json_script("scripts/demo/run_hf_space_package_smoke.py")
    checks["hf_space_local_package"] = {
        "ready": hf_package.get("ready", False),
        "errors": hf_package.get("errors", []),
    }

    langchain = _check_langchain_report()
    checks["langchain_benchmark"] = langchain

    docker = _check_docker_config()
    checks["docker_delivery"] = docker
    if docker["runtime_status"] == "runtime_not_verified":
        warnings.append("docker_runtime_not_verified_in_current_environment")

    ci = _check_ci_config()
    checks["github_actions_ci"] = ci

    documentation = _check_documentation()
    checks["documentation"] = documentation

    for name, result in checks.items():
        if not result.get("ready", False):
            blockers.append(f"{name}_not_ready")

    return {
        "ready": not blockers,
        "scope": "local_release_readiness",
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "hf_space_created": False,
        "hf_space_uploaded": False,
        "online_deployment_verified": False,
        "model_weights_included": False,
        "gpu_required": False,
        "api_key_required": False,
        "network_required_for_runtime": False,
        "langchain_benchmark_status": "ready" if langchain["ready"] else "not_ready",
        "docker_runtime_status": docker["runtime_status"],
        "ci_config_status": "ready" if ci["ready"] else "not_ready",
    }


def _check_model_lab() -> dict[str, Any]:
    root = PROJECT_ROOT / "demo" / "model_lab"
    manifest_path = root / "manifest.json"
    metrics_path = root / "layoutlmv3" / "metrics.json"
    if not manifest_path.exists() or not metrics_path.exists():
        return {"ready": False, "errors": ["required_model_lab_files_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    ready = (
        manifest.get("offline_only") is True
        and manifest.get("model_weights_included") is False
        and metrics.get("official_test") is False
    )
    return {
        "ready": ready,
        "offline_only": manifest.get("offline_only"),
        "model_weights_included": manifest.get("model_weights_included"),
        "official_test": metrics.get("official_test"),
    }


def _check_langchain_report() -> dict[str, Any]:
    path = PROJECT_ROOT / "reports" / "langchain" / "langchain_policy_rag_comparison.json"
    if not path.exists():
        return {"ready": False, "errors": ["benchmark_report_missing"]}
    payload = json.loads(path.read_text(encoding="utf-8"))
    ready = (
        payload.get("ready") is True
        and payload.get("case_count") == 8
        and payload.get("network_used") is False
        and payload.get("embedding_api_used") is False
        and payload.get("llm_api_used") is False
    )
    return {
        "ready": ready,
        "case_count": payload.get("case_count"),
        "summary": payload.get("summary"),
        "official_main_chain": payload.get("official_main_chain"),
    }


def _check_docker_config() -> dict[str, Any]:
    required = [PROJECT_ROOT / "Dockerfile", PROJECT_ROOT / "docker-compose.yml", PROJECT_ROOT / ".dockerignore"]
    config_ready = all(path.exists() for path in required)
    docker_available = shutil.which("docker") is not None
    return {
        "ready": config_ready,
        "config_ready": config_ready,
        "docker_cli_available": docker_available,
        "runtime_status": "runtime_not_verified" if not docker_available else "runtime_verification_pending",
    }


def _check_ci_config() -> dict[str, Any]:
    path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    if not path.exists():
        return {"ready": False, "errors": ["ci_workflow_missing"]}
    text = path.read_text(encoding="utf-8")
    required = [
        '.[demo,langchain,test]',
        "python -m pip check",
        "verify_portfolio_release_readiness.py",
        "python -m pytest tests -q",
    ]
    return {"ready": all(item in text for item in required), "workflow": ".github/workflows/ci.yml"}


def _check_documentation() -> dict[str, Any]:
    paths = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "LANGCHAIN_POLICY_RAG_COMPARISON.md",
        PROJECT_ROOT / "docs" / "ENGINEERING_DELIVERY.md",
        PROJECT_ROOT / "docs" / "HF_SPACES_DEPLOYMENT.md",
    ]
    missing = [path.relative_to(PROJECT_ROOT).as_posix() for path in paths if not path.exists()]
    hf_text = paths[-1].read_text(encoding="utf-8") if paths[-1].exists() else ""
    boundary_present = "当前没有创建 Hugging Face Space" in hf_text and "公网链接" in hf_text
    return {"ready": not missing and boundary_present, "missing": missing, "online_boundary_present": boundary_present}


def _run_json_script(relative: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, relative],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        return {"ready": False, "errors": [completed.stderr.strip() or f"script_failed:{relative}"]}
    return json.loads(completed.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify local portfolio release readiness.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = verify_release_readiness()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
