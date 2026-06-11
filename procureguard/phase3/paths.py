"""Phase 3 Notebook 和脚本共享的项目根目录解析。"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT_ENV = "PROCUREGUARD_PROJECT_ROOT"
PROJECT_DIR_NAME = "ProcureAgent"
PROJECT_MARKERS = ("pyproject.toml", "procureguard")
MODELSCOPE_PROJECT_ROOT = Path("/mnt/workspace") / PROJECT_DIR_NAME


def is_project_root(path: Path) -> bool:
    """使用项目标记判断目录是否为 ProcureGuard 仓库根目录。"""

    return (path / "pyproject.toml").is_file() and (path / "procureguard").is_dir()


def _append_candidate(candidates: list[Path], candidate: Path) -> None:
    """追加去重后的候选路径。"""

    resolved = candidate.expanduser().resolve()
    if resolved not in candidates:
        candidates.append(resolved)


def resolve_project_root(
    start: str | Path | None = None,
    *,
    notebook_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """按 ModelScope/Notebook 兼容顺序解析仓库根目录。"""

    env = os.environ if environ is None else environ
    start_path = Path(start or Path.cwd()).expanduser().resolve()
    candidates: list[Path] = []

    explicit = env.get(PROJECT_ROOT_ENV)
    if explicit:
        _append_candidate(candidates, Path(explicit))

    for candidate in (start_path, *start_path.parents):
        _append_candidate(candidates, candidate)

    if start_path.is_dir():
        _append_candidate(candidates, start_path / PROJECT_DIR_NAME)

    if notebook_path is not None:
        notebook = Path(notebook_path).expanduser().resolve()
        notebook_dir = notebook.parent if notebook.suffix else notebook
        _append_candidate(candidates, notebook_dir.parent)

    _append_candidate(candidates, MODELSCOPE_PROJECT_ROOT)

    for candidate in candidates:
        if is_project_root(candidate):
            return candidate

    attempted = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        "Cannot locate ProcureGuard project root. "
        f"Expected markers: {', '.join(PROJECT_MARKERS)}. "
        "Attempted paths:\n"
        + attempted
    )
