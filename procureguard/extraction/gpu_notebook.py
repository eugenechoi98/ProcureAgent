"""GPU Notebook 环境、数据路径修复和训练 guard 工具。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
from importlib import metadata
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
from typing import Callable, Iterable

from procureguard.extraction.alignment import align_sample_tokens
from procureguard.extraction.datasets import read_processed_jsonl


REQUIREMENT_IMPORTS = {
    "transformers": "transformers",
    "datasets": "datasets",
    "huggingface_hub": "huggingface_hub",
    "pillow": "PIL",
    "matplotlib": "matplotlib",
    "seqeval": "seqeval",
    "scikit-learn": "sklearn",
}
EXPECTED_TRAIN_SAMPLES = 570
EXPECTED_VALIDATION_SAMPLES = 142
DEFAULT_BASELINE_REPORT = Path("reports/phase1/baseline_sroie_task3_validation.json")
DEFAULT_BOOTSTRAP_REPORT = Path("reports/phase1/gpu_notebook_bootstrap.json")
COPY_SUFFIX_PATTERN = re.compile(r" \((?:1|2|3)\)$")


@dataclass(frozen=True)
class DependencyCheck:
    """GPU requirements 检查结果。"""

    installed: list[str]
    missing: list[str]


@dataclass(frozen=True)
class PathRepairResult:
    """单个 JSONL 的图片路径修复结果。"""

    path: Path
    sample_count: int
    changed: int
    unresolved: list[str]
    ambiguous: dict[str, list[str]]
    backup_path: Path | None


@dataclass(frozen=True)
class GpuNotebookSummary:
    """bootstrap 与 verify 共用的训练环境摘要。"""

    runtime: str
    python_executable: str
    python_version: str
    torch_version: str
    transformers_version: str
    seqeval_import_ok: bool
    cuda_available: bool
    gpu_name: str
    project_import_ok: bool
    project_root: str
    processed_dir: str
    image_root: str
    model_dir: str
    model_dir_exists: bool
    train_jsonl_exists: bool
    validation_jsonl_exists: bool
    train_samples: int
    validation_samples: int
    missing_images: int
    labels_non_o_count: int
    baseline_report_exists: bool
    baseline_report_path: str
    baseline_macro_f1: float | None
    training_guard_passed: bool


def parse_requirement_name(line: str) -> str | None:
    """从简单 requirements 行提取 distribution 名。"""

    cleaned = line.split("#", 1)[0].strip()
    if not cleaned or cleaned.startswith(("-", "git+", "http://", "https://")):
        return None
    match = re.match(r"([A-Za-z0-9_.-]+)", cleaned)
    return match.group(1).lower().replace("_", "-") if match else None


def read_requirement_names(path: str | Path) -> list[str]:
    """读取 GPU requirements 中声明的 distribution。"""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"GPU requirements file does not exist: {source}")
    names = [parse_requirement_name(line) for line in source.read_text(encoding="utf-8").splitlines()]
    return [name for name in names if name]


def check_requirements(
    requirement_names: Iterable[str],
    version_getter: Callable[[str], str] = metadata.version,
) -> DependencyCheck:
    """按 distribution 元数据检查依赖是否已安装。"""

    installed: list[str] = []
    missing: list[str] = []
    for name in requirement_names:
        try:
            version_getter(name)
            installed.append(name)
        except metadata.PackageNotFoundError:
            missing.append(name)
    return DependencyCheck(installed=installed, missing=missing)


def install_missing_requirements(
    missing: list[str],
    requirements_path: str | Path,
    *,
    python_executable: str = sys.executable,
    index_url: str = "https://pypi.org/simple",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """使用当前 Kernel Python 从明确 PyPI 源安装缺失依赖。"""

    if not missing:
        return
    command = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--index-url",
        index_url,
        "-r",
        str(Path(requirements_path)),
    ]
    try:
        runner(command, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        packages = ", ".join(missing)
        raise RuntimeError(
            "GPU dependency installation failed for "
            f"{packages}. The command used the current Notebook Kernel and {index_url}. "
            "If the network cannot reach PyPI, prepare wheels in a reachable location and run "
            f"`{python_executable} -m pip install --no-index --find-links <wheelhouse> "
            f"-r {requirements_path}` before rerunning bootstrap."
        ) from exc


def verify_dependency_imports(requirement_names: Iterable[str]) -> list[str]:
    """安装后立即验证每个 GPU 依赖都可以 import。"""

    failures: list[str] = []
    importlib.invalidate_caches()
    for name in requirement_names:
        module_name = REQUIREMENT_IMPORTS.get(name, name.replace("-", "_"))
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - 输出具体依赖导入错误
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    return failures


def install_project_for_kernel(
    project_root: str | Path,
    *,
    python_executable: str = sys.executable,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """将项目源码安装到当前 Notebook Kernel，不触发依赖解析。"""

    root = Path(project_root).resolve()
    runner(
        [python_executable, "-m", "pip", "install", "--no-deps", "-e", str(root)],
        check=True,
        text=True,
    )


def kernel_python_info() -> dict[str, str]:
    """返回 Notebook Kernel 的 Python 路径和版本。"""

    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
    }


def terminal_python_executable() -> str | None:
    """尽力探测 Terminal 默认 python，仅用于差异提示。"""

    return shutil.which("python")


def source_image_name(image_path: str) -> str:
    """兼容 Windows 和 Linux JSONL 图片路径并提取文件名。"""

    return PureWindowsPath(image_path).name if "\\" in image_path else Path(image_path).name


def normalize_copy_suffix(filename: str) -> str:
    """只归一化文件名末尾的 (1)、(2)、(3) 下载副本后缀。"""

    path = Path(filename)
    stem = COPY_SUFFIX_PATTERN.sub("", path.stem)
    return f"{stem}{path.suffix}".casefold()


def build_image_indexes(image_root: str | Path) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """为图片目录建立精确文件名和副本后缀索引。"""

    root = Path(image_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Image root does not exist: {root}")
    exact: dict[str, list[Path]] = {}
    normalized: dict[str, list[Path]] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        exact.setdefault(path.name.casefold(), []).append(path)
        normalized.setdefault(normalize_copy_suffix(path.name), []).append(path)
    return exact, normalized


def resolve_image_path(
    original_path: str,
    exact_index: dict[str, list[Path]],
    normalized_index: dict[str, list[Path]],
) -> tuple[Path | None, list[Path]]:
    """优先精确匹配，再安全匹配末尾副本后缀。"""

    filename = source_image_name(original_path)
    exact = exact_index.get(filename.casefold(), [])
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, exact
    candidates = normalized_index.get(normalize_copy_suffix(filename), [])
    if len(candidates) == 1:
        return candidates[0], []
    return None, candidates


def backup_jsonl(path: str | Path) -> Path:
    """首次修复前创建不可覆盖的原始 JSONL 备份。"""

    source = Path(path)
    backup = source.with_suffix(source.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(source, backup)
    return backup


def repair_processed_jsonl_paths(
    jsonl_path: str | Path,
    image_root: str | Path,
) -> PathRepairResult:
    """解析、校验并原子修复 processed JSONL 的图片路径。"""

    path = Path(jsonl_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Processed JSONL does not exist: {path}")
    exact_index, normalized_index = build_image_indexes(image_root)
    rows: list[dict[str, object]] = []
    unresolved: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    changed = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                sample_id = str(row["sample_id"])
                original_path = str(row["image_path"])
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid processed JSONL line {path}:{line_number}.") from exc
            resolved, candidates = resolve_image_path(original_path, exact_index, normalized_index)
            if resolved is None:
                if candidates:
                    ambiguous[sample_id] = [str(candidate) for candidate in candidates]
                else:
                    unresolved.append(sample_id)
            else:
                resolved_text = str(resolved)
                if original_path != resolved_text:
                    row["image_path"] = resolved_text
                    changed += 1
            rows.append(row)

    if unresolved or ambiguous:
        return PathRepairResult(path, len(rows), changed, unresolved, ambiguous, None)
    backup = backup_jsonl(path)
    if changed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    return PathRepairResult(path, len(rows), changed, [], {}, backup)


def require_successful_repairs(results: Iterable[PathRepairResult]) -> None:
    """存在 unresolved 或 ambiguous 图片时停止 bootstrap。"""

    unresolved = {
        str(result.path): result.unresolved for result in results if result.unresolved
    }
    ambiguous = {
        str(result.path): result.ambiguous for result in results if result.ambiguous
    }
    if unresolved or ambiguous:
        raise RuntimeError(
            "Image path repair failed. "
            f"unresolved={json.dumps(unresolved, ensure_ascii=False)}; "
            f"ambiguous={json.dumps(ambiguous, ensure_ascii=False)}"
        )


def count_non_o_labels(samples: Iterable[object]) -> int:
    """使用真实 SroieSample 对齐逻辑统计非 O 标签。"""

    count = 0
    for sample in samples:
        labels, _ = align_sample_tokens(sample)  # type: ignore[arg-type]
        count += sum(label != "O" for label in labels)
    return count


def load_baseline_macro_f1(path: str | Path) -> float | None:
    """从现有 baseline 报告读取 macro F1。"""

    source = Path(path)
    if not source.is_file():
        return None
    report = json.loads(source.read_text(encoding="utf-8"))
    for metric in report.get("metrics", []):
        if metric.get("field") == "macro":
            return float(metric["f1"])
    raise ValueError(f"Baseline report has no macro metric: {source}")


def model_directory_exists(path: str | Path) -> bool:
    """检查本地模型目录，训练时不触发 Hugging Face 网络访问。"""

    return Path(path).is_dir()


def evaluate_training_guard(
    *,
    cuda_available: bool,
    require_cuda: bool,
    project_import_ok: bool,
    model_dir_exists: bool,
    train_samples: int,
    validation_samples: int,
    missing_images: int,
    labels_non_o_count: int,
    baseline_report_exists: bool,
    seqeval_import_ok: bool,
) -> bool:
    """统一判断是否允许进入训练。"""

    return all(
        [
            cuda_available if require_cuda else True,
            project_import_ok,
            model_dir_exists,
            train_samples == EXPECTED_TRAIN_SAMPLES,
            validation_samples == EXPECTED_VALIDATION_SAMPLES,
            missing_images == 0,
            labels_non_o_count > 0,
            baseline_report_exists,
            seqeval_import_ok,
        ]
    )


def inspect_runtime_versions() -> dict[str, object]:
    """读取训练依赖和 CUDA 环境版本。"""

    try:
        torch = importlib.import_module("torch")
    except ImportError as exc:
        raise RuntimeError(
            "Torch is missing from the Notebook Kernel. Select a ModelScope or Colab GPU "
            "runtime that already provides a CUDA-compatible torch build; bootstrap will not "
            "replace the platform torch package."
        ) from exc
    transformers = importlib.import_module("transformers")
    try:
        importlib.import_module("seqeval")
        seqeval_import_ok = True
    except ImportError:
        seqeval_import_ok = False
    cuda_available = bool(torch.cuda.is_available())
    return {
        "torch_version": str(torch.__version__),
        "transformers_version": str(transformers.__version__),
        "seqeval_import_ok": seqeval_import_ok,
        "cuda_available": cuda_available,
        "gpu_name": str(torch.cuda.get_device_name(0)) if cuda_available else "",
    }


def build_gpu_notebook_summary(
    *,
    project_root: str | Path,
    processed_dir: str | Path,
    image_root: str | Path,
    model_dir: str | Path,
    runtime: str,
    require_cuda: bool = True,
) -> GpuNotebookSummary:
    """只读检查环境、样本和训练 guard。"""

    root = Path(project_root).resolve()
    processed = Path(processed_dir).resolve()
    images = Path(image_root).resolve()
    model = Path(model_dir).resolve()
    train_path = processed / "train.jsonl"
    validation_path = processed / "validation.jsonl"
    baseline_path = root / DEFAULT_BASELINE_REPORT
    versions = inspect_runtime_versions()

    train_samples = read_processed_jsonl(train_path) if train_path.is_file() else []
    validation_samples = read_processed_jsonl(validation_path) if validation_path.is_file() else []
    all_samples = [*train_samples, *validation_samples]
    missing_images = sum(not Path(sample.image_path).is_file() for sample in all_samples)
    labels_non_o_count = count_non_o_labels(train_samples)
    baseline_exists = baseline_path.is_file()
    model_exists = model_directory_exists(model)
    project_import_ok = importlib.util.find_spec("procureguard") is not None
    guard_passed = evaluate_training_guard(
        cuda_available=bool(versions["cuda_available"]),
        require_cuda=require_cuda,
        project_import_ok=project_import_ok,
        model_dir_exists=model_exists,
        train_samples=len(train_samples),
        validation_samples=len(validation_samples),
        missing_images=missing_images,
        labels_non_o_count=labels_non_o_count,
        baseline_report_exists=baseline_exists,
        seqeval_import_ok=bool(versions["seqeval_import_ok"]),
    )
    return GpuNotebookSummary(
        runtime=runtime,
        **kernel_python_info(),
        torch_version=str(versions["torch_version"]),
        transformers_version=str(versions["transformers_version"]),
        seqeval_import_ok=bool(versions["seqeval_import_ok"]),
        cuda_available=bool(versions["cuda_available"]),
        gpu_name=str(versions["gpu_name"]),
        project_import_ok=project_import_ok,
        project_root=str(root),
        processed_dir=str(processed),
        image_root=str(images),
        model_dir=str(model),
        model_dir_exists=model_exists,
        train_jsonl_exists=train_path.is_file(),
        validation_jsonl_exists=validation_path.is_file(),
        train_samples=len(train_samples),
        validation_samples=len(validation_samples),
        missing_images=missing_images,
        labels_non_o_count=labels_non_o_count,
        baseline_report_exists=baseline_exists,
        baseline_report_path=str(baseline_path),
        baseline_macro_f1=load_baseline_macro_f1(baseline_path),
        training_guard_passed=guard_passed,
    )


def summary_to_dict(summary: GpuNotebookSummary) -> dict[str, object]:
    """将环境摘要转换为稳定 JSON 字典。"""

    return asdict(summary)


def write_summary(summary: GpuNotebookSummary, path: str | Path) -> Path:
    """写出 Notebook 可恢复的 bootstrap 摘要。"""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def print_summary(summary: GpuNotebookSummary) -> None:
    """逐行输出用户要求的环境验证字段。"""

    for key, value in summary_to_dict(summary).items():
        if isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = value
        print(f"{key}={rendered}")
