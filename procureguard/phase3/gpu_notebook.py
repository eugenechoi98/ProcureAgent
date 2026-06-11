"""Phase 3 LoRA Notebook bootstrap、verify 和推理 smoke guard。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import random
import sys
from typing import Any

from procureguard.phase3.runtime import build_runtime_context, runtime_config_dict


FALLBACK_MODULES = ("torch", "transformers", "datasets", "accelerate", "peft", "trl")
OPTIONAL_MODULES = ("unsloth", "bitsandbytes")
PROJECT_DEPENDENCY_MODULES = ("pydantic",)
DATASET_FILES = ("train.jsonl", "validation.jsonl", "test.jsonl")
DEFAULT_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
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

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "procureguard").exists():
            return candidate
    raise FileNotFoundError("未找到 ProcureGuard 项目根目录")


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


def phase3_paths(
    project_root: Path | None = None,
    artifact_dir: Path | None = None,
    model_dir: str | None = None,
) -> Phase3Paths:
    """构建 Notebook 和脚本共享的路径集合。"""

    root = (project_root or find_project_root()).resolve()
    artifacts = (artifact_dir or root / "artifacts" / "phase3").resolve()
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

    return {
        "torch_import_ok": True,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "cuda_device_name": torch.cuda.get_device_name(0)
        if torch.cuda.is_available()
        else None,
    }


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
) -> dict[str, Any]:
    """生成 Notebook bootstrap/verify 统一 guard。"""

    if write:
        ensure_output_dirs(paths)
    project_dependencies = assert_project_dependencies()
    dataset = verify_dataset_hashes(paths)
    torch_info = torch_environment()
    missing_fallback = module_missing(FALLBACK_MODULES)
    optional_versions = package_versions(OPTIONAL_MODULES)
    fallback_versions = package_versions(FALLBACK_MODULES)
    backend = (
        "unsloth"
        if prefer_unsloth and util.find_spec("unsloth") is not None
        else "transformers_peft"
    )
    model_guard = model_dir_guard(paths.model_dir)
    guard = {
        "python_executable": sys.executable,
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
        "prefer_unsloth": prefer_unsloth,
        "fallback_missing": missing_fallback,
        "fallback_versions": fallback_versions,
        "optional_versions": optional_versions,
        "project_dependencies": project_dependencies,
        "torch": torch_info,
        "dataset": dataset,
        "model_dir": model_guard,
        "require_cuda": require_cuda,
        "training_ready": dataset["ok"]
        and not missing_fallback
        and model_guard["ready"]
        and (torch_info["cuda_available"] or not require_cuda),
    }
    return guard


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
) -> dict[str, Any]:
    """恢复 Notebook Kernel 的数据、配置与输出目录上下文。"""

    assert_project_dependencies()
    paths = phase3_paths(project_root=project_root, artifact_dir=artifact_dir, model_dir=model_dir)
    guard = notebook_guard(paths, prefer_unsloth=prefer_unsloth, write=True)
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
