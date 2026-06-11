"""解析并检查 Phase 1G Notebook checkpoint inference 路径。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_MARKERS = ("pyproject.toml", "AGENTS.md", "procureguard")


@dataclass(frozen=True)
class Phase1GPaths:
    """Phase 1G 独立推理所需的全部仓库内路径。"""

    project_root: Path
    script: Path
    checkpoint: Path
    validation: Path
    image_root: Path
    baseline_report: Path
    output_dir: Path


def is_project_root(path: Path) -> bool:
    """使用项目标记判断候选目录是否为仓库根目录。"""

    return (
        (path / "pyproject.toml").is_file()
        and (path / "AGENTS.md").is_file()
        and (path / "procureguard").is_dir()
    )


def resolve_project_root(
    start: str | Path,
    *,
    notebook_path: str | Path | None = None,
) -> Path:
    """从当前目录、父目录、直接子目录或 Notebook 位置查找仓库根目录。"""

    start_path = Path(start).expanduser().resolve()
    seeds = [start_path]
    if notebook_path is not None:
        notebook = Path(notebook_path).expanduser().resolve()
        seeds.append(notebook.parent if notebook.suffix else notebook)

    checked: list[Path] = []
    for seed in seeds:
        for candidate in (seed, *seed.parents):
            if candidate not in checked:
                checked.append(candidate)
                if is_project_root(candidate):
                    return candidate

    if start_path.is_dir():
        for candidate in sorted(path for path in start_path.iterdir() if path.is_dir()):
            checked.append(candidate)
            if is_project_root(candidate):
                return candidate

    preview = ", ".join(str(path) for path in checked[:8])
    raise FileNotFoundError(
        "Cannot locate ProcureAgent project root. "
        f"Expected markers {PROJECT_MARKERS}; checked: {preview}"
    )


def build_phase1g_paths(project_root: str | Path) -> Phase1GPaths:
    """基于仓库根目录生成 Phase 1G 的绝对路径。"""

    root = Path(project_root).expanduser().resolve()
    return Phase1GPaths(
        project_root=root,
        script=root / "scripts" / "phase1" / "compare_date_reconstruction.py",
        checkpoint=root / "checkpoints" / "phase1" / "layoutlmv3_best",
        validation=root / "data" / "phase1" / "sroie_task3" / "processed" / "validation.jsonl",
        image_root=root / "data" / "phase1" / "sroie_task3" / "data",
        baseline_report=root / "reports" / "phase1" / "baseline_sroie_task3_validation.json",
        output_dir=root / "reports" / "phase1" / "checkpoint_inference",
    )


def require_phase1g_paths(paths: Phase1GPaths) -> Phase1GPaths:
    """在启动子进程前一次性检查 Phase 1G 输入并创建输出目录。"""

    required = {
        "script": (paths.script, "file"),
        "checkpoint": (paths.checkpoint, "directory"),
        "checkpoint model.safetensors": (paths.checkpoint / "model.safetensors", "file"),
        "validation JSONL": (paths.validation, "file"),
        "image root": (paths.image_root, "directory"),
        "baseline report": (paths.baseline_report, "file"),
    }
    missing = []
    for label, (path, kind) in required.items():
        exists = path.is_file() if kind == "file" else path.is_dir()
        if not exists:
            missing.append(f"{label}: {path}")
    if missing:
        raise FileNotFoundError(
            "Phase 1G checkpoint inference inputs are incomplete:\n"
            + "\n".join(missing)
        )
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    return paths
