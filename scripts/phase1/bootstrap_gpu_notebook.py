"""一次性准备 Phase 1 GPU Notebook Kernel、数据和训练 guard。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def parse_args() -> argparse.Namespace:
    """解析 bootstrap 路径和运行环境参数。"""

    parser = argparse.ArgumentParser(description="Bootstrap the Phase 1 GPU Notebook.")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--image-root", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--runtime", choices=["modelscope", "colab"], required=True)
    parser.add_argument("--index-url", default="https://pypi.org/simple")
    return parser.parse_args()


def main() -> None:
    """安装当前 Kernel 依赖、修复路径并输出统一训练 guard。"""

    args = parse_args()
    project_root = args.project_root.resolve()
    if not (project_root / "pyproject.toml").is_file():
        raise SystemExit(f"Invalid project root: {project_root}")
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from procureguard.extraction.gpu_notebook import (
        DEFAULT_BOOTSTRAP_REPORT,
        build_gpu_notebook_summary,
        check_requirements,
        install_missing_requirements,
        install_project_for_kernel,
        print_summary,
        read_requirement_names,
        repair_processed_jsonl_paths,
        require_safetensors_model,
        require_successful_repairs,
        terminal_python_executable,
        verify_dependency_imports,
        write_summary,
    )

    requirements_path = project_root / "requirements" / "phase1-gpu.txt"
    requirement_names = read_requirement_names(requirements_path)
    dependencies = check_requirements(requirement_names)
    print(f"kernel_python={sys.executable}")
    print(f"terminal_python={terminal_python_executable() or 'not_found'}")
    if terminal_python_executable() and Path(terminal_python_executable()).resolve() != Path(sys.executable).resolve():
        print("warning=Terminal python differs from Notebook Kernel; the Kernel is the training source of truth.")
    print(f"dependencies_installed={dependencies.installed}")
    print(f"dependencies_missing={dependencies.missing}")

    install_missing_requirements(
        dependencies.missing,
        requirements_path,
        python_executable=sys.executable,
        index_url=args.index_url,
    )
    import_failures = verify_dependency_imports(requirement_names)
    if import_failures:
        raise SystemExit("Dependency import verification failed: " + "; ".join(import_failures))
    print(f"dependencies_install_success={dependencies.missing}")
    print("dependencies_import_verified=true")

    install_project_for_kernel(project_root, python_executable=sys.executable)
    require_safetensors_model(args.model_dir)
    train_repair = repair_processed_jsonl_paths(args.processed_dir / "train.jsonl", args.image_root)
    validation_repair = repair_processed_jsonl_paths(
        args.processed_dir / "validation.jsonl",
        args.image_root,
    )
    require_successful_repairs([train_repair, validation_repair])
    print(f"train_paths_changed={train_repair.changed}")
    print(f"validation_paths_changed={validation_repair.changed}")
    print(f"train_backup={train_repair.backup_path or 'not_needed'}")
    print(f"validation_backup={validation_repair.backup_path or 'not_needed'}")

    summary = build_gpu_notebook_summary(
        project_root=project_root,
        processed_dir=args.processed_dir,
        image_root=args.image_root,
        model_dir=args.model_dir,
        runtime=args.runtime,
    )
    report_path = write_summary(summary, project_root / DEFAULT_BOOTSTRAP_REPORT)
    print_summary(summary)
    print(f"bootstrap_report={report_path}")
    if not summary.model_dir_exists:
        raise SystemExit(
            "Local LayoutLMv3 model.safetensors is missing. Download it before training; "
            "bootstrap will not use pytorch_model.bin or contact Hugging Face automatically."
        )
    if not summary.training_guard_passed:
        raise SystemExit("training_guard_passed=false; fix the reported checks before training.")


if __name__ == "__main__":
    main()
