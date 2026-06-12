"""Phase 3 LoRA Notebook bootstrap、verify 和推理 smoke guard。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import random
import platform
import subprocess
import sys
from typing import Any

from procureguard.phase3.paths import resolve_project_root
from procureguard.phase3.runtime import build_runtime_context, runtime_config_dict


FALLBACK_MODULES = ("torch", "transformers", "datasets", "accelerate", "peft", "trl")
OPTIONAL_MODULES = ("unsloth", "bitsandbytes")
PROJECT_DEPENDENCY_MODULES = ("pydantic",)
DATASET_FILES = ("train.jsonl", "validation.jsonl", "test.jsonl")
DEFAULT_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_MODELSCOPE_MODEL_DIR = "/mnt/workspace/models/phase3/Qwen2.5-0.5B-Instruct"
DEFAULT_MODELSCOPE_KERNEL_PYTHON = "/mnt/workspace/ProcureAgent/.venv-phase3/bin/python"
DEFAULT_PHASE3_ARTIFACT_DIR = "artifacts/phase3"
RECOMMENDED_PHASE3G_ARTIFACT_DIR = "artifacts/phase3_runs/phase3g_second_lora_run"
TRAINING_BACKEND = "qlora_4bit_bitsandbytes"
PROJECT_DEPENDENCY_HELP = (
    "Missing ProcureGuard project dependency modules: {missing}. "
    "Activate .venv-phase3, then run: python -m pip install -e ."
)


@dataclass(frozen=True)
class Phase3Paths:
    """Phase 3 Notebook 的统一路径。"""

    project_root: Path
    data_dir: Path
    summary_path: Path
    requirements_path: Path
    artifact_dir: Path
    adapter_dir: Path
    log_dir: Path
    prediction_dir: Path
    evaluation_dir: Path
    trainer_dir: Path
    model_cache_dir: Path
    model_dir: Path | None = None


def find_project_root(start: Path | None = None) -> Path:
    """从当前目录向上寻找项目根目录。"""

    return resolve_project_root(start)


def default_model_cache_dir(project_root: Path) -> Path:
    """解析 Hugging Face / ModelScope 可复用的模型缓存目录。"""

    for env_name in ("PHASE3_MODEL_CACHE", "HF_HOME", "MODELSCOPE_CACHE"):
        value = os.environ.get(env_name)
        if value:
            return Path(value).expanduser().resolve()
    return (project_root / "models_cache" / "phase3").resolve()


def resolve_model_dir(project_root: Path, explicit_model_dir: str | None = None) -> Path | None:
    """解析本地 Qwen 模型目录，未提供时返回 None。"""

    value = explicit_model_dir or os.environ.get("PHASE3_MODEL_DIR")
    if value:
        return Path(value).expanduser().resolve()
    candidates = [
        default_model_cache_dir(project_root) / "Qwen2.5-0.5B-Instruct",
        project_root / "models_cache" / "phase3" / "Qwen2.5-0.5B-Instruct",
        project_root / "models_cache" / "Qwen2.5-0.5B-Instruct",
    ]
    return next((path.resolve() for path in candidates if path.exists()), None)


def notebook_model_dir_from_env(environ: dict[str, str] | None = None) -> str:
    """Notebook 使用环境变量优先、ModelScope 默认值兜底的模型目录。"""

    env = os.environ if environ is None else environ
    return env.get("PHASE3_MODEL_DIR", DEFAULT_MODELSCOPE_MODEL_DIR)


def notebook_kernel_python_from_env(environ: dict[str, str] | None = None) -> str:
    """Notebook 使用环境变量优先、ModelScope 默认值兜底的 Kernel Python。"""

    env = os.environ if environ is None else environ
    return env.get("PHASE3_KERNEL_PYTHON", DEFAULT_MODELSCOPE_KERNEL_PYTHON)


def resolve_artifact_dir(
    project_root: Path,
    explicit_artifact_dir: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """解析 Phase 3 输出目录，显式参数优先，其次 PHASE3_ARTIFACT_DIR。"""

    env = os.environ if environ is None else environ
    value = explicit_artifact_dir or env.get("PHASE3_ARTIFACT_DIR")
    if value:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else project_root / path).resolve()
    return (project_root / DEFAULT_PHASE3_ARTIFACT_DIR).resolve()


def notebook_artifact_dir_from_env(
    project_root: Path,
    environ: dict[str, str] | None = None,
) -> str:
    """Notebook 使用环境变量优先、Phase 3G 独立 run 目录兜底。"""

    env = os.environ if environ is None else environ
    value = env.get("PHASE3_ARTIFACT_DIR", RECOMMENDED_PHASE3G_ARTIFACT_DIR)
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else project_root / path).resolve())


def phase3_paths(
    project_root: Path | None = None,
    artifact_dir: Path | None = None,
    model_dir: str | None = None,
) -> Phase3Paths:
    """构建 Notebook 和脚本共享的路径集合。"""

    root = (project_root or find_project_root()).resolve()
    artifacts = resolve_artifact_dir(root, artifact_dir)
    return Phase3Paths(
        project_root=root,
        data_dir=root / "data" / "phase3" / "generated",
        summary_path=root / "reports" / "phase3" / "dataset_summary.json",
        requirements_path=root / "requirements" / "phase3-lora.txt",
        artifact_dir=artifacts,
        adapter_dir=artifacts / "adapters" / "qwen2.5-0.5b-anomaly-explainer",
        log_dir=artifacts / "logs",
        prediction_dir=artifacts / "predictions",
        evaluation_dir=artifacts / "evaluation",
        trainer_dir=artifacts / "trainer",
        model_cache_dir=default_model_cache_dir(root),
        model_dir=resolve_model_dir(root, model_dir),
    )


def ensure_output_dirs(paths: Phase3Paths) -> list[str]:
    """创建本地 artifacts 输出目录。"""

    created: list[str] = []
    for path in (
        paths.artifact_dir,
        paths.adapter_dir,
        paths.log_dir,
        paths.prediction_dir,
        paths.evaluation_dir,
        paths.trainer_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path))
    return created


def package_versions(names: tuple[str, ...]) -> dict[str, str | None]:
    """读取包版本，未安装时返回 None。"""

    result: dict[str, str | None] = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def module_missing(names: tuple[str, ...]) -> list[str]:
    """检查模块是否可 import。"""

    return [name for name in names if util.find_spec(name) is None]


def project_dependency_guard() -> dict[str, Any]:
    """检查 ProcureGuard 默认项目依赖是否已安装。"""

    missing = module_missing(PROJECT_DEPENDENCY_MODULES)
    return {
        "required_modules": list(PROJECT_DEPENDENCY_MODULES),
        "missing": missing,
        "ok": not missing,
        "install_hint": "python -m pip install -e .",
    }


def assert_project_dependencies() -> dict[str, Any]:
    """缺少默认项目依赖时给出明确安装提示。"""

    guard = project_dependency_guard()
    if not guard["ok"]:
        raise RuntimeError(
            PROJECT_DEPENDENCY_HELP.format(missing=", ".join(guard["missing"]))
        )
    return guard


def torch_environment() -> dict[str, Any]:
    """读取 Torch/CUDA 状态，不强制要求本机有 GPU。"""

    if util.find_spec("torch") is None:
        return {"torch_import_ok": False, "cuda_available": False}
    import torch

    cuda_available = False
    cuda_device_count = 0
    cuda_device_name = None
    cuda_error = None
    try:
        cuda_available = torch.cuda.is_available()
        cuda_device_count = torch.cuda.device_count() if cuda_available else 0
        cuda_device_name = torch.cuda.get_device_name(0) if cuda_available else None
    except Exception as exc:  # noqa: BLE001
        cuda_error = str(exc)
    return {
        "torch_import_ok": True,
        "torch_version": torch.__version__,
        "torch_file": str(Path(torch.__file__).resolve()),
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": cuda_available,
        "cuda_device_count": cuda_device_count,
        "cuda_device_name": cuda_device_name,
        "cuda_error": cuda_error,
    }


def numpy_environment() -> dict[str, Any]:
    """检查 NumPy ABI 是否兼容当前 Torch CUDA 运行时。"""

    install_hint = "python -m pip install -r requirements/phase3-lora.txt"
    if util.find_spec("numpy") is None:
        return {
            "installed": False,
            "import_ok": False,
            "version": None,
            "major_version": None,
            "numpy_abi_ready": False,
            "error": "numpy is not installed",
            "install_hint": install_hint,
        }
    try:
        import numpy as np

        version = np.__version__
        major_version = int(version.split(".", maxsplit=1)[0])
        return {
            "installed": True,
            "import_ok": True,
            "version": version,
            "major_version": major_version,
            "numpy_abi_ready": major_version < 2,
            "file": str(Path(np.__file__).resolve()),
            "error": None,
            "install_hint": install_hint,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "installed": True,
            "import_ok": False,
            "version": package_versions(("numpy",)).get("numpy"),
            "major_version": None,
            "numpy_abi_ready": False,
            "error": str(exc),
            "install_hint": install_hint,
        }


def bitsandbytes_environment() -> dict[str, Any]:
    """检查 bitsandbytes 是否满足 4-bit QLoRA 训练路径。"""

    if util.find_spec("bitsandbytes") is None:
        return {
            "installed": False,
            "import_ok": False,
            "version": None,
            "cuda_available": False,
            "error": "bitsandbytes is not installed",
        }
    try:
        import bitsandbytes as bnb

        cuda_available = False
        cuda_specs = None
        cuda_error = None
        try:
            from bitsandbytes.cuda_specs import get_cuda_specs

            cuda_specs = get_cuda_specs()
            cuda_available = cuda_specs is not None
        except Exception as exc:  # noqa: BLE001
            cuda_error = str(exc)
        return {
            "installed": True,
            "import_ok": True,
            "version": getattr(bnb, "__version__", None),
            "file": str(Path(bnb.__file__).resolve()),
            "cuda_available": cuda_available,
            "cuda_specs": str(cuda_specs) if cuda_specs is not None else None,
            "error": cuda_error,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "installed": True,
            "import_ok": False,
            "version": package_versions(("bitsandbytes",)).get("bitsandbytes"),
            "cuda_available": False,
            "error": str(exc),
        }


def nvidia_smi_summary() -> dict[str, Any]:
    """读取 nvidia-smi 摘要，不修改环境。"""

    command = ["nvidia-smi"]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found"}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def kernel_python_guard(expected_kernel_python: str | None = None) -> dict[str, Any]:
    """检查 Notebook Kernel Python 是否和预期虚拟环境一致。"""

    actual = Path(sys.executable).expanduser().resolve()
    if not expected_kernel_python:
        return {
            "expected": None,
            "actual": str(actual),
            "matches": True,
        }
    expected = Path(expected_kernel_python).expanduser().resolve()
    return {
        "expected": str(expected),
        "actual": str(actual),
        "matches": actual == expected,
    }


def preflight_failed_checks(
    *,
    dataset: dict[str, Any],
    project_dependencies: dict[str, Any],
    missing_fallback: list[str],
    model_guard: dict[str, Any],
    kernel_guard: dict[str, Any] | None = None,
) -> list[str]:
    """汇总不依赖 CUDA 的基础 preflight 失败项。"""

    failed: list[str] = []
    if not dataset["ok"]:
        failed.append("data_sha_guard")
    if not project_dependencies["ok"]:
        failed.append("project_dependencies")
    if missing_fallback:
        failed.append("phase3_lora_dependencies")
    if not model_guard["ready"]:
        failed.append("model_dir")
    if kernel_guard is not None and not kernel_guard["matches"]:
        failed.append("kernel_python")
    return failed


def training_failed_checks(
    *,
    preflight_failed: list[str],
    torch_info: dict[str, Any],
    numpy_info: dict[str, Any],
    bitsandbytes_info: dict[str, Any],
) -> list[str]:
    """汇总真实训练门禁失败项，始终检查 CUDA、NumPy ABI 与 bitsandbytes。"""

    failed = list(preflight_failed)
    if not numpy_info.get("numpy_abi_ready"):
        failed.append("numpy_abi")
    if not torch_info.get("cuda_available"):
        failed.append("cuda_available")
    if int(torch_info.get("cuda_device_count") or 0) <= 0:
        failed.append("cuda_device_count")
    if not bitsandbytes_info.get("import_ok"):
        failed.append("bitsandbytes_import")
    if not bitsandbytes_info.get("cuda_available"):
        failed.append("bitsandbytes_cuda")
    return failed


def verify_dataset_hashes(paths: Phase3Paths) -> dict[str, Any]:
    """核对 generated JSONL 与 dataset_summary.json 中的 SHA-256。"""

    if not paths.summary_path.exists():
        raise FileNotFoundError(f"缺少数据摘要: {paths.summary_path}")
    summary = json.loads(paths.summary_path.read_text(encoding="utf-8"))
    results: dict[str, dict[str, Any]] = {}
    for name in DATASET_FILES:
        path = paths.data_dir / name
        if not path.exists():
            results[name] = {"exists": False, "sha256_ok": False}
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = summary["sha256"].get(name)
        results[name] = {
            "exists": True,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "sha256_ok": actual == expected,
        }
    ok = all(item["exists"] and item["sha256_ok"] for item in results.values())
    return {
        "ok": ok,
        "sample_count": summary.get("sample_count"),
        "split_counts": summary.get("split_counts"),
        "files": results,
    }


def model_dir_guard(model_dir: Path | None) -> dict[str, Any]:
    """检查本地 Qwen base 模型目录是否足够支持离线 smoke。"""

    if model_dir is None:
        return {
            "configured": False,
            "exists": False,
            "ready": False,
            "message": "PHASE3_MODEL_DIR is not configured; base inference smoke stays dry-run.",
        }
    required = ("config.json", "tokenizer_config.json")
    has_required = {name: (model_dir / name).exists() for name in required}
    tokenizer_candidates = ("tokenizer.json", "tokenizer.model", "vocab.json")
    tokenizer_files = {
        name: (model_dir / name).exists() for name in tokenizer_candidates
    }
    safetensors = sorted(path.name for path in model_dir.glob("*.safetensors"))
    safetensors_index_path = model_dir / "model.safetensors.index.json"
    safetensors_index = safetensors_index_path.exists()
    indexed_shards: list[str] = []
    missing_indexed_shards: list[str] = []
    index_valid = True
    if safetensors_index:
        try:
            index = json.loads(safetensors_index_path.read_text(encoding="utf-8"))
            indexed_shards = sorted(set(index.get("weight_map", {}).values()))
            missing_indexed_shards = [
                name for name in indexed_shards if not (model_dir / name).exists()
            ]
        except json.JSONDecodeError:
            index_valid = False
            missing_indexed_shards = ["<invalid model.safetensors.index.json>"]
    if safetensors_index:
        weights_ready = index_valid and bool(indexed_shards) and not missing_indexed_shards
    else:
        weights_ready = bool(safetensors)
    return {
        "configured": True,
        "path": str(model_dir),
        "exists": model_dir.exists(),
        "required_files": has_required,
        "tokenizer_files": tokenizer_files,
        "safetensors_files": safetensors,
        "safetensors_index": safetensors_index,
        "safetensors_index_valid": index_valid if safetensors_index else None,
        "indexed_shards": indexed_shards,
        "missing_indexed_shards": missing_indexed_shards,
        "ready": model_dir.exists()
        and all(has_required.values())
        and any(tokenizer_files.values())
        and weights_ready,
    }


def notebook_guard(
    paths: Phase3Paths,
    require_cuda: bool = False,
    prefer_unsloth: bool = True,
    write: bool = False,
    expected_kernel_python: str | None = None,
) -> dict[str, Any]:
    """生成 Notebook bootstrap/verify 统一 guard。"""

    if write:
        ensure_output_dirs(paths)
    project_dependencies = assert_project_dependencies()
    dataset = verify_dataset_hashes(paths)
    torch_info = torch_environment()
    numpy_info = numpy_environment()
    bitsandbytes_info = bitsandbytes_environment()
    missing_fallback = module_missing(FALLBACK_MODULES)
    optional_versions = package_versions(OPTIONAL_MODULES)
    fallback_versions = package_versions(FALLBACK_MODULES)
    backend = (
        "unsloth"
        if prefer_unsloth and util.find_spec("unsloth") is not None
        else "transformers_peft"
    )
    model_guard = model_dir_guard(paths.model_dir)
    kernel_guard = kernel_python_guard(expected_kernel_python)
    preflight_failed = preflight_failed_checks(
        dataset=dataset,
        project_dependencies=project_dependencies,
        missing_fallback=missing_fallback,
        model_guard=model_guard,
        kernel_guard=kernel_guard,
    )
    failed_checks = training_failed_checks(
        preflight_failed=preflight_failed,
        torch_info=torch_info,
        numpy_info=numpy_info,
        bitsandbytes_info=bitsandbytes_info,
    )
    guard = {
        "python_executable": sys.executable,
        "kernel_python": kernel_guard,
        "project_root": str(paths.project_root),
        "requirements_path": str(paths.requirements_path),
        "artifact_dir": str(paths.artifact_dir),
        "adapter_dir": str(paths.adapter_dir),
        "log_dir": str(paths.log_dir),
        "prediction_dir": str(paths.prediction_dir),
        "evaluation_dir": str(paths.evaluation_dir),
        "model_cache_dir": str(paths.model_cache_dir),
        "model_id": DEFAULT_MODEL_ID,
        "backend": backend,
        "training_backend": TRAINING_BACKEND,
        "prefer_unsloth": prefer_unsloth,
        "fallback_missing": missing_fallback,
        "fallback_versions": fallback_versions,
        "optional_versions": optional_versions,
        "project_dependencies": project_dependencies,
        "torch": torch_info,
        "numpy": numpy_info,
        "bitsandbytes": bitsandbytes_info,
        "dataset": dataset,
        "model_dir": model_guard,
        "require_cuda": require_cuda,
        "preflight_failed_checks": preflight_failed,
        "preflight_ready": not preflight_failed,
        "failed_checks": failed_checks,
        "training_ready": not failed_checks,
    }
    return guard


def cuda_runtime_diagnostics(
    project_root: Path | None = None,
    model_dir: str | None = None,
    expected_kernel_python: str | None = None,
) -> dict[str, Any]:
    """输出 Phase 3 CUDA runtime 只读诊断信息。"""

    root = project_root or find_project_root()
    paths = phase3_paths(root, model_dir=model_dir)
    torch_info = torch_environment()
    numpy_info = numpy_environment()
    bitsandbytes_info = bitsandbytes_environment()
    project_dependencies = project_dependency_guard()
    missing_fallback = module_missing(FALLBACK_MODULES)
    model_guard = model_dir_guard(paths.model_dir)
    dataset = verify_dataset_hashes(paths)
    kernel_guard = kernel_python_guard(expected_kernel_python)
    preflight_failed = preflight_failed_checks(
        dataset=dataset,
        project_dependencies=project_dependencies,
        missing_fallback=missing_fallback,
        model_guard=model_guard,
        kernel_guard=kernel_guard,
    )
    failed_checks = training_failed_checks(
        preflight_failed=preflight_failed,
        torch_info=torch_info,
        numpy_info=numpy_info,
        bitsandbytes_info=bitsandbytes_info,
    )
    return {
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "project_root": str(paths.project_root),
        "model_dir": str(paths.model_dir) if paths.model_dir else None,
        "phase3_model_dir_env": os.environ.get("PHASE3_MODEL_DIR"),
        "kernel_python": kernel_guard,
        "training_backend": TRAINING_BACKEND,
        "torch_version": torch_info.get("torch_version"),
        "torch_cuda_version": torch_info.get("torch_cuda_version"),
        "cuda_available": torch_info.get("cuda_available"),
        "cuda_device_count": torch_info.get("cuda_device_count"),
        "numpy_version": numpy_info.get("version"),
        "numpy_abi_ready": numpy_info.get("numpy_abi_ready"),
        "bitsandbytes_version": bitsandbytes_info.get("version"),
        "torch": torch_info,
        "numpy": numpy_info,
        "nvidia_smi": nvidia_smi_summary(),
        "transformers_version": package_versions(("transformers",)).get("transformers"),
        "peft_version": package_versions(("peft",)).get("peft"),
        "bitsandbytes": bitsandbytes_info,
        "dataset": dataset,
        "model_guard": model_guard,
        "project_dependencies": project_dependencies,
        "fallback_missing": missing_fallback,
        "preflight_ready": not preflight_failed,
        "training_ready": not failed_checks,
        "failed_checks": failed_checks,
    }


def write_guard_report(paths: Phase3Paths, guard: dict[str, Any], filename: str) -> Path:
    """把 guard 写入 artifacts/phase3/logs。"""

    paths.log_dir.mkdir(parents=True, exist_ok=True)
    output = paths.log_dir / filename
    output.write_text(
        json.dumps(guard, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def bootstrap_notebook(
    project_root: Path | None = None,
    require_cuda: bool = False,
    model_dir: str | None = None,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """可写 bootstrap：创建 artifacts，设置随机种子并写 guard。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    random.seed(42)
    guard = notebook_guard(paths, require_cuda=require_cuda, write=True)
    guard["created_output_dirs"] = ensure_output_dirs(paths)
    guard["guard_report"] = str(write_guard_report(paths, guard, "environment_guard.json"))
    return guard


def notebook_runtime_guard(
    project_root: Path | None = None,
    require_cuda: bool = False,
    model_dir: str | None = None,
    expected_kernel_python: str | None = None,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Notebook 专用 runtime guard，写独立报告，不覆盖 Terminal bootstrap。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    guard = notebook_guard(
        paths,
        require_cuda=require_cuda,
        write=True,
        expected_kernel_python=expected_kernel_python,
    )
    guard["created_output_dirs"] = ensure_output_dirs(paths)
    guard["guard_report"] = str(
        write_guard_report(paths, guard, "notebook_runtime_guard.json")
    )
    return guard


def verify_notebook_env(
    project_root: Path | None = None,
    require_cuda: bool = False,
    model_dir: str | None = None,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """只读 verify：不创建目录、不安装依赖、不下载模型。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    return notebook_guard(paths, require_cuda=require_cuda, write=False)


def hydrate_runtime_context(
    project_root: Path | None = None,
    model_dir: str | None = None,
    prefer_unsloth: bool = True,
    artifact_dir: Path | None = None,
    require_cuda: bool = False,
    expected_kernel_python: str | None = None,
) -> dict[str, Any]:
    """恢复 Notebook Kernel 的数据、配置与输出目录上下文。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    guard = notebook_guard(
        paths,
        require_cuda=require_cuda,
        prefer_unsloth=prefer_unsloth,
        write=True,
        expected_kernel_python=expected_kernel_python,
    )
    guard["guard_report"] = str(
        write_guard_report(paths, guard, "notebook_runtime_guard.json")
    )
    context = build_runtime_context(
        paths.project_root,
        backend=guard["backend"],
        model_id=DEFAULT_MODEL_ID,
        seed=42,
    )
    config = runtime_config_dict(context)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    (paths.log_dir / "training_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "paths": {key: str(value) if value is not None else None for key, value in paths.__dict__.items()},
        "guard": guard,
        "context": context,
        "config": config,
    }


def build_base_inference_plan(
    project_root: Path | None = None,
    model_dir: str | None = None,
    sample_count: int = 1,
    artifact_dir: Path | None = None,
    output_name: str = "base_smoke.jsonl",
) -> dict[str, Any]:
    """生成 base inference smoke 的可执行计划。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    model_guard = model_dir_guard(paths.model_dir)
    return {
        "model_id": DEFAULT_MODEL_ID,
        "model_dir": model_guard,
        "input_path": str(paths.data_dir / "test.jsonl"),
        "output_path": str(paths.prediction_dir / output_name),
        "sample_count": sample_count,
        "generation": {"max_new_tokens": 256, "do_sample": False},
        "dry_run_safe": True,
    }


def run_base_inference_smoke(
    project_root: Path | None = None,
    model_dir: str | None = None,
    sample_count: int = 1,
    run: bool = False,
    artifact_dir: Path | None = None,
    output_name: str = "base_smoke.jsonl",
) -> dict[str, Any]:
    """默认 dry-run；显式 run=True 时才加载 base model 生成少量预测。"""

    assert_project_dependencies()
    plan = build_base_inference_plan(
        project_root,
        model_dir,
        sample_count,
        artifact_dir,
        output_name=output_name,
    )
    if not run:
        plan["status"] = "dry_run"
        return plan
    if not plan["model_dir"]["ready"]:
        raise RuntimeError("base inference smoke 需要可用的本地 PHASE3_MODEL_DIR")

    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    from procureguard.phase3.runtime import read_jsonl, to_messages, write_predictions_jsonl

    rows = read_jsonl(Path(plan["input_path"]))[:sample_count]
    tokenizer = AutoTokenizer.from_pretrained(plan["model_dir"]["path"], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        plan["model_dir"]["path"],
        local_files_only=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None,
    )
    explanations: list[str] = []
    for row in rows:
        prompt = tokenizer.apply_chat_template(
            to_messages(row, include_answer=False),
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=plan["generation"]["max_new_tokens"],
                do_sample=plan["generation"]["do_sample"],
            )
        new_tokens = output_ids[0, inputs["input_ids"].shape[-1] :]
        explanations.append(tokenizer.decode(new_tokens, skip_special_tokens=True).strip())
    write_predictions_jsonl(Path(plan["output_path"]), rows, explanations)
    plan["status"] = "completed"
    return plan
