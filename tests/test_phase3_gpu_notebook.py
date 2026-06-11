"""Phase 3B LoRA Notebook runtime guard 测试。"""

import json
from pathlib import Path
import subprocess
import sys

import procureguard.phase3.gpu_notebook as gpu_notebook
from procureguard.phase3.gpu_notebook import (
    assert_project_dependencies,
    bootstrap_notebook,
    build_base_inference_plan,
    cuda_runtime_diagnostics,
    find_project_root,
    hydrate_runtime_context,
    model_dir_guard,
    notebook_guard,
    notebook_kernel_python_from_env,
    notebook_model_dir_from_env,
    notebook_runtime_guard,
    numpy_environment,
    phase3_paths,
    preflight_failed_checks,
    training_failed_checks,
    verify_dataset_hashes,
    verify_notebook_env,
)
from procureguard.phase3.paths import resolve_project_root
from procureguard.phase3.runtime import write_artifacts_manifest


NUMPY_1_READY = {"version": "1.26.4", "major_version": 1, "numpy_abi_ready": True}
NUMPY_2_NOT_READY = {"version": "2.4.6", "major_version": 2, "numpy_abi_ready": False}


def write_minimum_model_files(model_dir: Path) -> None:
    """写入模型目录 guard 需要的最小非权重文件。"""

    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")


def write_project_markers(root: Path) -> None:
    """写入 resolver 识别项目根目录所需的最小标记。"""

    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "procureguard").mkdir()


def test_resolve_project_root_from_repo_root(tmp_path: Path):
    repo = tmp_path / "ProcureAgent"
    write_project_markers(repo)

    assert resolve_project_root(repo, environ={}) == repo.resolve()


def test_resolve_project_root_from_repo_child(tmp_path: Path):
    repo = tmp_path / "ProcureAgent"
    write_project_markers(repo)
    child = repo / "notebooks"
    child.mkdir()

    assert resolve_project_root(child, environ={}) == repo.resolve()


def test_resolve_project_root_from_parent_with_procureagent_child(tmp_path: Path):
    repo = tmp_path / "ProcureAgent"
    write_project_markers(repo)

    assert resolve_project_root(tmp_path, environ={}) == repo.resolve()


def test_resolve_project_root_from_explicit_env(tmp_path: Path):
    repo = tmp_path / "CustomRepo"
    write_project_markers(repo)

    assert (
        resolve_project_root(
            tmp_path / "elsewhere",
            environ={"PROCUREGUARD_PROJECT_ROOT": str(repo)},
        )
        == repo.resolve()
    )


def test_resolve_project_root_from_notebook_path(tmp_path: Path):
    repo = tmp_path / "ProcureAgent"
    write_project_markers(repo)
    notebook = repo / "notebooks" / "phase3_lora_explainer_training.ipynb"
    notebook.parent.mkdir()
    notebook.write_text("{}", encoding="utf-8")

    assert resolve_project_root(tmp_path / "other", notebook_path=notebook, environ={}) == repo.resolve()


def test_resolve_project_root_failure_lists_attempted_paths(tmp_path: Path):
    try:
        resolve_project_root(tmp_path, environ={})
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("resolve_project_root should fail without project markers")

    assert "Attempted paths" in message
    assert str(tmp_path.resolve()) in message


def test_dataset_sha_guard_matches_summary():
    root = find_project_root(Path.cwd())
    paths = phase3_paths(root)

    result = verify_dataset_hashes(paths)

    assert result["ok"] is True
    assert result["sample_count"] == 200
    assert result["split_counts"] == {"test": 20, "train": 160, "validation": 20}
    assert all(item["sha256_ok"] for item in result["files"].values())


def test_bootstrap_creates_output_dirs_and_writes_guard(tmp_path: Path):
    root = find_project_root(Path.cwd())
    paths = phase3_paths(root, artifact_dir=tmp_path)

    guard = bootstrap_notebook(root, require_cuda=False, artifact_dir=tmp_path)
    isolated_guard = verify_notebook_env(root, require_cuda=False, artifact_dir=tmp_path)
    for output_dir in (
        paths.adapter_dir,
        paths.log_dir,
        paths.prediction_dir,
        paths.evaluation_dir,
        paths.trainer_dir,
    ):
        assert output_dir.exists()

    assert guard["dataset"]["ok"] is True
    assert Path(guard["guard_report"]).exists()
    assert isolated_guard["dataset"]["ok"] is True


def test_notebook_runtime_guard_does_not_overwrite_bootstrap_report(tmp_path: Path):
    root = find_project_root(Path.cwd())

    bootstrap = bootstrap_notebook(root, require_cuda=False, artifact_dir=tmp_path)
    bootstrap_report = Path(bootstrap["guard_report"])
    before = bootstrap_report.read_text(encoding="utf-8")
    runtime = notebook_runtime_guard(root, require_cuda=False, artifact_dir=tmp_path)

    assert bootstrap_report.name == "environment_guard.json"
    assert Path(runtime["guard_report"]).name == "notebook_runtime_guard.json"
    assert bootstrap_report.read_text(encoding="utf-8") == before


def test_project_dependency_guard_reports_missing_pydantic(monkeypatch):
    original_find_spec = gpu_notebook.util.find_spec

    def fake_find_spec(name: str):
        if name == "pydantic":
            return None
        return original_find_spec(name)

    monkeypatch.setattr(gpu_notebook.util, "find_spec", fake_find_spec)

    try:
        assert_project_dependencies()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("assert_project_dependencies should fail when pydantic is missing")

    assert "pydantic" in message
    assert "python -m pip install -e ." in message


def test_phase3_virtualenv_is_gitignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".venv-phase3/" in gitignore


def test_notebook_defaults_modelscope_paths_when_env_missing():
    assert (
        notebook_model_dir_from_env({})
        == "/mnt/workspace/models/phase3/Qwen2.5-0.5B-Instruct"
    )
    assert (
        notebook_kernel_python_from_env({})
        == "/mnt/workspace/ProcureAgent/.venv-phase3/bin/python"
    )


def test_notebook_env_overrides_modelscope_defaults():
    env = {
        "PHASE3_MODEL_DIR": "/custom/model",
        "PHASE3_KERNEL_PYTHON": "/custom/python",
    }

    assert notebook_model_dir_from_env(env) == "/custom/model"
    assert notebook_kernel_python_from_env(env) == "/custom/python"


def test_preflight_and_training_ready_are_separate():
    preflight = preflight_failed_checks(
        dataset={"ok": True},
        project_dependencies={"ok": True},
        missing_fallback=[],
        model_guard={"ready": True},
        kernel_guard={"matches": True},
    )

    training = training_failed_checks(
        preflight_failed=preflight,
        torch_info={"cuda_available": False, "cuda_device_count": 0},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert preflight == []
    assert "cuda_available" in training


def test_training_failed_checks_include_cuda_even_before_run_training():
    failed = training_failed_checks(
        preflight_failed=[],
        torch_info={"cuda_available": False, "cuda_device_count": 0},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert "cuda_available" in failed
    assert "cuda_device_count" in failed


def test_training_failed_checks_include_model_dir_when_not_ready():
    preflight = preflight_failed_checks(
        dataset={"ok": True},
        project_dependencies={"ok": True},
        missing_fallback=[],
        model_guard={"ready": False},
        kernel_guard={"matches": True},
    )
    failed = training_failed_checks(
        preflight_failed=preflight,
        torch_info={"cuda_available": True, "cuda_device_count": 1},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert failed == ["model_dir"]


def test_training_failed_checks_ready_when_all_training_guards_pass():
    failed = training_failed_checks(
        preflight_failed=[],
        torch_info={"cuda_available": True, "cuda_device_count": 1},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert failed == []


def test_training_failed_checks_include_bitsandbytes_cuda():
    failed = training_failed_checks(
        preflight_failed=[],
        torch_info={"cuda_available": True, "cuda_device_count": 1},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": False, "cuda_available": False},
    )

    assert "bitsandbytes_import" in failed
    assert "bitsandbytes_cuda" in failed


def test_numpy_1_26_training_guard_is_ready():
    failed = training_failed_checks(
        preflight_failed=[],
        torch_info={"cuda_available": True, "cuda_device_count": 1},
        numpy_info=NUMPY_1_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert failed == []


def test_numpy_2_training_guard_is_not_ready():
    failed = training_failed_checks(
        preflight_failed=[],
        torch_info={"cuda_available": True, "cuda_device_count": 1},
        numpy_info=NUMPY_2_NOT_READY,
        bitsandbytes_info={"import_ok": True, "cuda_available": True},
    )

    assert "numpy_abi" in failed


def test_numpy_environment_reports_local_abi_state():
    info = numpy_environment()

    assert "version" in info
    assert "major_version" in info
    assert "numpy_abi_ready" in info
    assert "install_hint" in info


def test_notebook_guard_training_ready_when_all_checks_pass(tmp_path: Path, monkeypatch):
    root = find_project_root(Path.cwd())
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"fake")
    paths = phase3_paths(root, artifact_dir=tmp_path / "artifacts", model_dir=str(model_dir))

    monkeypatch.setattr(gpu_notebook, "module_missing", lambda names: [])
    monkeypatch.setattr(
        gpu_notebook,
        "torch_environment",
        lambda: {
            "torch_import_ok": True,
            "cuda_available": True,
            "cuda_device_count": 1,
            "cuda_device_name": "fake-cuda",
        },
    )
    monkeypatch.setattr(
        gpu_notebook,
        "bitsandbytes_environment",
        lambda: {"import_ok": True, "cuda_available": True},
    )
    monkeypatch.setattr(gpu_notebook, "numpy_environment", lambda: NUMPY_1_READY)

    guard = notebook_guard(
        paths,
        require_cuda=True,
        expected_kernel_python=sys.executable,
    )

    assert guard["training_ready"] is True
    assert guard["preflight_ready"] is True
    assert guard["failed_checks"] == []


def test_notebook_guard_training_not_ready_without_cuda(tmp_path: Path, monkeypatch):
    root = find_project_root(Path.cwd())
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"fake")
    paths = phase3_paths(root, artifact_dir=tmp_path / "artifacts", model_dir=str(model_dir))

    monkeypatch.setattr(gpu_notebook, "module_missing", lambda names: [])
    monkeypatch.setattr(
        gpu_notebook,
        "torch_environment",
        lambda: {
            "torch_import_ok": True,
            "cuda_available": False,
            "cuda_device_count": 0,
            "cuda_device_name": None,
        },
    )
    monkeypatch.setattr(
        gpu_notebook,
        "bitsandbytes_environment",
        lambda: {"import_ok": True, "cuda_available": True},
    )
    monkeypatch.setattr(gpu_notebook, "numpy_environment", lambda: NUMPY_1_READY)

    guard = notebook_guard(
        paths,
        require_cuda=True,
        expected_kernel_python=sys.executable,
    )

    assert guard["training_ready"] is False
    assert guard["preflight_ready"] is True
    assert "cuda_available" in guard["failed_checks"]


def test_notebook_guard_checks_numpy_abi_before_training_switch(tmp_path: Path, monkeypatch):
    root = find_project_root(Path.cwd())
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"fake")
    paths = phase3_paths(root, artifact_dir=tmp_path / "artifacts", model_dir=str(model_dir))

    monkeypatch.setattr(gpu_notebook, "module_missing", lambda names: [])
    monkeypatch.setattr(
        gpu_notebook,
        "torch_environment",
        lambda: {
            "torch_import_ok": True,
            "cuda_available": True,
            "cuda_device_count": 1,
            "cuda_device_name": "fake-cuda",
        },
    )
    monkeypatch.setattr(
        gpu_notebook,
        "bitsandbytes_environment",
        lambda: {"import_ok": True, "cuda_available": True},
    )
    monkeypatch.setattr(gpu_notebook, "numpy_environment", lambda: NUMPY_2_NOT_READY)

    guard = notebook_guard(
        paths,
        require_cuda=True,
        expected_kernel_python=sys.executable,
    )

    assert guard["preflight_ready"] is True
    assert guard["training_ready"] is False
    assert "numpy_abi" in guard["failed_checks"]


def test_cuda_runtime_diagnostics_outputs_required_fields(tmp_path: Path, monkeypatch):
    root = find_project_root(Path.cwd())
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"fake")

    monkeypatch.setattr(
        gpu_notebook,
        "torch_environment",
        lambda: {
            "torch_import_ok": True,
            "torch_version": "2.2.2+cu118",
            "torch_file": "/fake/torch/__init__.py",
            "torch_cuda_version": "11.8",
            "cuda_available": False,
            "cuda_device_count": 0,
            "cuda_device_name": None,
            "cuda_error": "driver too old",
        },
    )
    monkeypatch.setattr(
        gpu_notebook,
        "bitsandbytes_environment",
        lambda: {
            "installed": True,
            "import_ok": False,
            "version": "0.44.1",
            "cuda_available": False,
            "error": "no cuda",
        },
    )
    monkeypatch.setattr(gpu_notebook, "numpy_environment", lambda: NUMPY_2_NOT_READY)
    monkeypatch.setattr(gpu_notebook, "nvidia_smi_summary", lambda: {"available": False})

    report = cuda_runtime_diagnostics(
        root,
        model_dir=str(model_dir),
        expected_kernel_python=sys.executable,
    )

    assert report["python_executable"] == sys.executable
    assert "platform" in report
    assert report["torch_version"] == "2.2.2+cu118"
    assert report["torch_cuda_version"] == "11.8"
    assert report["cuda_available"] is False
    assert report["cuda_device_count"] == 0
    assert report["numpy_version"] == "2.4.6"
    assert report["numpy_abi_ready"] is False
    assert report["bitsandbytes_version"] == "0.44.1"
    assert report["torch"]["torch_version"] == "2.2.2+cu118"
    assert report["numpy"]["version"] == "2.4.6"
    assert "nvidia_smi" in report
    assert "bitsandbytes" in report
    assert "transformers_version" in report
    assert "peft_version" in report
    assert report["training_backend"] == "qlora_4bit_bitsandbytes"
    assert report["training_ready"] is False
    assert "cuda_available" in report["failed_checks"]
    assert "numpy_abi" in report["failed_checks"]


def test_diagnose_cuda_runtime_script_outputs_json():
    result = subprocess.run(
        [sys.executable, "scripts/phase3/diagnose_cuda_runtime.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    for key in (
        "python_executable",
        "platform",
        "torch",
        "nvidia_smi",
        "transformers_version",
        "peft_version",
        "bitsandbytes",
        "numpy_version",
        "numpy_abi_ready",
        "torch_version",
        "torch_cuda_version",
        "cuda_available",
        "cuda_device_count",
        "bitsandbytes_version",
        "training_backend",
        "training_ready",
        "failed_checks",
    ):
        assert key in payload


def test_model_dir_guard_requires_config_tokenizer_and_safetensors(tmp_path: Path):
    missing = model_dir_guard(None)
    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    incomplete = model_dir_guard(model_dir)
    (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")
    ready = model_dir_guard(model_dir)

    assert missing["ready"] is False
    assert incomplete["ready"] is False
    assert ready["ready"] is True


def test_model_dir_guard_single_safetensors_ready_without_index(tmp_path: Path):
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors").write_bytes(b"fake")

    guard = model_dir_guard(model_dir)

    assert guard["ready"] is True
    assert guard["safetensors_index"] is False


def test_model_dir_guard_index_ready_when_all_shards_exist(tmp_path: Path):
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "a": "model-00001-of-00002.safetensors",
                    "b": "model-00002-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "model-00001-of-00002.safetensors").write_bytes(b"fake")
    (model_dir / "model-00002-of-00002.safetensors").write_bytes(b"fake")

    guard = model_dir_guard(model_dir)

    assert guard["ready"] is True
    assert guard["indexed_shards"] == [
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
    ]


def test_model_dir_guard_index_missing_any_shard_not_ready(tmp_path: Path):
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "a": "model-00001-of-00002.safetensors",
                    "b": "model-00002-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "model-00001-of-00002.safetensors").write_bytes(b"fake")

    guard = model_dir_guard(model_dir)

    assert guard["ready"] is False
    assert guard["missing_indexed_shards"] == ["model-00002-of-00002.safetensors"]


def test_model_dir_guard_index_takes_priority_over_partial_safetensors(tmp_path: Path):
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "a": "model-00001-of-00002.safetensors",
                    "b": "model-00002-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "model-00001-of-00002.safetensors").write_bytes(b"fake")
    (model_dir / "unrelated.safetensors").write_bytes(b"fake")

    guard = model_dir_guard(model_dir)

    assert guard["ready"] is False
    assert guard["safetensors_index"] is True
    assert guard["missing_indexed_shards"] == ["model-00002-of-00002.safetensors"]


def test_model_dir_guard_invalid_index_not_ready(tmp_path: Path):
    model_dir = tmp_path / "qwen"
    write_minimum_model_files(model_dir)
    (model_dir / "model.safetensors.index.json").write_text("{not-json", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"fake")

    guard = model_dir_guard(model_dir)

    assert guard["ready"] is False
    assert guard["safetensors_index_valid"] is False
    assert guard["missing_indexed_shards"] == ["<invalid model.safetensors.index.json>"]


def test_hydrate_runtime_context_loads_fixed_splits(tmp_path: Path):
    root = find_project_root(Path.cwd())

    runtime = hydrate_runtime_context(root, artifact_dir=tmp_path)
    context = runtime["context"]

    assert len(context.train_rows) == 160
    assert len(context.validation_rows) == 20
    assert len(context.test_rows) == 20
    assert runtime["config"]["model_id"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert runtime["config"]["generation"]["do_sample"] is False


def test_base_inference_plan_is_dry_run_without_model_dir(tmp_path: Path):
    root = find_project_root(Path.cwd())

    plan = build_base_inference_plan(
        root,
        sample_count=1,
        artifact_dir=tmp_path,
        output_name="base.jsonl",
    )

    assert plan["dry_run_safe"] is True
    assert plan["sample_count"] == 1
    assert plan["model_dir"]["ready"] is False
    assert plan["output_path"].endswith("base.jsonl")


def test_artifacts_manifest_records_files_and_adapter_dir(tmp_path: Path):
    output_file = tmp_path / "predictions" / "base.jsonl"
    output_file.parent.mkdir()
    output_file.write_text('{"sample_id":"x","explanation":"ok"}\n', encoding="utf-8")
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")

    manifest = write_artifacts_manifest(
        tmp_path / "artifacts_manifest.json",
        {"base_predictions": output_file, "missing_report": tmp_path / "missing.json"},
        adapter_dir=adapter_dir,
    )

    assert manifest["files"]["base_predictions"]["exists"] is True
    assert manifest["files"]["base_predictions"]["sha256"]
    assert manifest["files"]["missing_report"]["exists"] is False
    assert manifest["adapter_dir"]["file_count"] == 1


def test_prepare_qwen_model_is_dry_run_by_default(tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/phase3/prepare_qwen_model.py",
            "--model-dir",
            str(tmp_path / "qwen"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["download_requested"] is False
    assert payload["guard"]["ready"] is False
    assert "offline_upload_instructions" in payload


def test_notebook_uses_unified_runtime_guard_and_default_no_training():
    notebook = json.loads(
        Path("notebooks/phase3_lora_explainer_training.ipynb").read_text(encoding="utf-8")
    )
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "RUN_TRAINING = False" in text
    assert "RUN_BASE_SMOKE = False" in text
    assert "notebook_model_dir_from_env" in text
    assert "notebook_kernel_python_from_env" in text
    assert "os.environ.get('PHASE3_MODEL_DIR')" not in text
    assert "from procureguard.phase3.paths import resolve_project_root" in text
    assert "def resolve_project_root" not in text
    assert "notebook_runtime_guard" in text
    assert "require_cuda=REQUIRE_CUDA_FOR_TRAINING" in text
    assert "require_cuda=RUN_TRAINING and REQUIRE_CUDA_FOR_TRAINING" not in text
    assert "hydrate_runtime_context" in text
    assert "run_base_inference_smoke" in text
    assert "missing_modules = [" not in text
