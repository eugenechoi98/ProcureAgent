"""Phase 3B LoRA Notebook runtime guard 测试。"""

import json
from pathlib import Path

from procureguard.phase3.gpu_notebook import (
    bootstrap_notebook,
    build_base_inference_plan,
    find_project_root,
    hydrate_runtime_context,
    model_dir_guard,
    phase3_paths,
    verify_dataset_hashes,
    verify_notebook_env,
)


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


def test_model_dir_guard_requires_config_tokenizer_and_safetensors(tmp_path: Path):
    missing = model_dir_guard(None)
    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    incomplete = model_dir_guard(model_dir)
    (model_dir / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
    ready = model_dir_guard(model_dir)

    assert missing["ready"] is False
    assert incomplete["ready"] is False
    assert ready["ready"] is True


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

    plan = build_base_inference_plan(root, sample_count=1, artifact_dir=tmp_path)

    assert plan["dry_run_safe"] is True
    assert plan["sample_count"] == 1
    assert plan["model_dir"]["ready"] is False
    assert plan["output_path"].endswith("base_smoke.jsonl")


def test_notebook_uses_unified_runtime_guard_and_default_no_training():
    notebook = json.loads(
        Path("notebooks/phase3_lora_explainer_training.ipynb").read_text(encoding="utf-8")
    )
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "RUN_TRAINING = False" in text
    assert "RUN_BASE_SMOKE = False" in text
    assert "bootstrap_notebook" in text
    assert "hydrate_runtime_context" in text
    assert "run_base_inference_smoke" in text
    assert "missing_modules = [" not in text
