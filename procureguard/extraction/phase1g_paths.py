"""解析并检查 Phase 1G Notebook checkpoint inference 路径。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


PROJECT_MARKERS = ("pyproject.toml", "AGENTS.md", "procureguard")
IMAGE_ROOT_ENV_NAMES = ("PROCUREGUARD_PHASE1G_IMAGE_ROOT", "SROIE_IMAGE_ROOT")


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


def resolve_image_root(
    project_root: str | Path,
    *,
    explicit: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    workspace_root: str | Path | None = None,
) -> Path:
    """按显式配置、环境变量、ModelScope 和仓库候选解析图片目录。"""

    root = Path(project_root).expanduser().resolve()
    environment = os.environ if environ is None else environ
    workspace = (
        Path(workspace_root).expanduser().resolve()
        if workspace_root is not None
        else root.parent
    )
    candidates: list[tuple[str, Path]] = []
    if explicit is not None:
        candidates.append(("explicit", Path(explicit).expanduser().resolve()))
    for name in IMAGE_ROOT_ENV_NAMES:
        value = environment.get(name)
        if value:
            candidates.append((f"environment {name}", Path(value).expanduser().resolve()))
    candidates.extend(
        [
            (
                "ModelScope workspace",
                workspace / "SROIE" / "unpacked" / "sroie" / "imgs",
            ),
            (
                "repository task3 data",
                root / "data" / "phase1" / "sroie_task3" / "data",
            ),
            (
                "repository SROIE inbox",
                root
                / "data"
                / "phase1"
                / "sroie"
                / "inbox"
                / "SROIE"
                / "unpacked"
                / "sroie"
                / "imgs",
            ),
        ]
    )

    attempted: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for source, candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        attempted.append((source, candidate))
        if candidate.is_dir():
            return candidate
    details = "\n".join(f"- {source}: {path}" for source, path in attempted)
    raise FileNotFoundError(
        "Cannot locate Phase 1G image root. Tried paths in priority order:\n"
        + details
    )


def build_phase1g_paths(
    project_root: str | Path,
    *,
    image_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    workspace_root: str | Path | None = None,
) -> Phase1GPaths:
    """基于仓库根目录生成 Phase 1G 的绝对路径。"""

    root = Path(project_root).expanduser().resolve()
    return Phase1GPaths(
        project_root=root,
        script=root / "scripts" / "phase1" / "compare_date_reconstruction.py",
        checkpoint=root / "checkpoints" / "phase1" / "layoutlmv3_best",
        validation=root / "data" / "phase1" / "sroie_task3" / "processed" / "validation.jsonl",
        image_root=resolve_image_root(
            root,
            explicit=image_root,
            environ=environ,
            workspace_root=workspace_root,
        ),
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
