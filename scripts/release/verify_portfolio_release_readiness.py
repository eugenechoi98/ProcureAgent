"""聚合验证 ProcureGuard AI 本地作品集发布准备状态。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.demo.run_unified_portfolio_demo_smoke import run_smoke as run_unified_smoke


def verify_release_readiness(*, include_online_check: bool = False) -> dict[str, Any]:
    """聚合本地交付证据；仅显式启用时访问公网。"""

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

    deployment = _check_deployment_report(include_online_check=include_online_check)
    checks["hf_spaces_public_deployment"] = deployment
    if deployment.get("manual_browser_check_required"):
        warnings.append("hf_spaces_manual_visual_browser_check_required")

    for name, result in checks.items():
        if not result.get("ready", False):
            blockers.append(f"{name}_not_ready")

    return {
        "ready": not blockers,
        "scope": "local_release_readiness",
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "hf_space_created": deployment.get("hf_space_created", False),
        "hf_space_uploaded": deployment.get("hf_space_uploaded", False),
        "online_deployment_verified": deployment.get("online_deployment_verified", False),
        "manual_browser_check_required": deployment.get("manual_browser_check_required", True),
        "model_lab_presentation_polished": deployment.get("model_lab_presentation_polished", False),
        "manual_visual_check": deployment.get("manual_visual_check"),
        "production_ready": deployment.get("production_ready", False),
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
    boundary_present = (
        "https://huggingface.co/spaces/eugene-98/procureguard-ai-demo" in hf_text
        and "在线 LayoutLMv3" in hf_text
    )
    return {"ready": not missing and boundary_present, "missing": missing, "online_boundary_present": boundary_present}


def _check_deployment_report(*, include_online_check: bool) -> dict[str, Any]:
    path = PROJECT_ROOT / "reports" / "deployment" / "hf_spaces_public_deployment.json"
    if not path.exists():
        return {
            "ready": False,
            "hf_space_created": False,
            "hf_space_uploaded": False,
            "online_deployment_verified": False,
            "manual_browser_check_required": True,
            "errors": ["deployment_report_missing"],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    ready = (
        payload.get("visibility") == "public"
        and payload.get("build_status") == "success"
        and payload.get("runtime_status") == "running_cpu_basic"
        and payload.get("localized_ui") is True
        and payload.get("model_lab_presentation_polished") is True
        and payload.get("online_deployment_verified") is True
        and payload.get("manual_browser_check_required") is False
        and payload.get("checks", {}).get("manual_visual_check") == "passed"
        and payload.get("checks", {}).get("frontend_errors") is False
        and payload.get("remote_forbidden_hits") == []
        and payload.get("model_weights_included") is False
    )
    result = {
        "ready": ready,
        "hf_space_created": True,
        "hf_space_uploaded": True,
        "online_deployment_verified": payload.get("online_deployment_verified", False),
        "manual_browser_check_required": payload.get("manual_browser_check_required", True),
        "hub_url": payload.get("space_hub_url"),
        "app_url": payload.get("space_app_url"),
        "remote_commit": payload.get("remote_commit"),
        "runtime_status": payload.get("runtime_status"),
        "localized_ui": payload.get("localized_ui", False),
        "model_lab_presentation_polished": payload.get("model_lab_presentation_polished", False),
        "manual_visual_check": payload.get("checks", {}).get("manual_visual_check"),
        "production_ready": payload.get("production_ready", False),
        "online_check_included": include_online_check,
    }
    if include_online_check:
        result["online_http"] = _check_public_urls(
            payload["space_hub_url"], payload["space_app_url"]
        )
        result["ready"] = ready and result["online_http"]["ready"]
    return result


def _check_public_urls(hub_url: str, app_url: str) -> dict[str, Any]:
    statuses: dict[str, int | None] = {}
    for name, url in {
        "hub": hub_url,
        "app": app_url,
        "config": f"{app_url.rstrip('/')}/config",
    }.items():
        try:
            with urlopen(url, timeout=30) as response:
                statuses[name] = response.status
        except OSError:
            statuses[name] = None
    return {"ready": all(value == 200 for value in statuses.values()), "statuses": statuses}


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
    parser.add_argument(
        "--include-online-check",
        action="store_true",
        help="Also check the public Hub, App, and Gradio config URLs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    result = verify_release_readiness(include_online_check=args.include_online_check)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
