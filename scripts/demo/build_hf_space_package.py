"""构建 Hugging Face Spaces 最小本地发布包。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPACE_ROOT = PROJECT_ROOT / "spaces" / "procureguard_demo"

README_TEXT = """---
title: ProcureGuard AI
emoji: 🧾
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
---

# ProcureGuard AI

ProcureGuard AI 是采购发票智能审核 Agent 的 CPU-only 作品集 Demo。

页面包含：

1. Path A 手动审核：无 ML，手动字段直接进入确定性审核
2. Path B Scenario Demo：5 个案例，每个案例都有图片、Run Audit 和 Audit Result
3. 系统说明：架构、边界和 trace/log 说明

当前公开 Demo：

- 不加载 LayoutLMv3
- 不加载 Qwen
- 不加载真实 LoRA
- 不需要 GPU
- 不需要 API Key
- 不需要 secrets
- Path B 展示流程驱动 UI，不使用纯文本案例页
- 5 个案例都有发票图片、Run Audit 按钮和结果卡片
- 每张发票图片绑定唯一 scenario_id，Run Audit 会加载该 scenario 的固定字段映射
- 所有 scenario OCR 字段均为非空值，不展示空字段或失败状态
- LoRA OFF/ON 切换放在 Audit Result 内部，不再单独作为页面
- AI 图片链路是预置场景驱动展示，不是网页实时推理

## 运行边界

发票图片会绑定固定 scenario_id；字段展示、审计输入和解释文本均来自该 scenario
的预置映射。页面不调用 OCR 模型、不调用 LayoutLMv3、不随机生成字段。LoRA 只做
解释语言增强，不影响 risk_level 或 recommended_action。当前没有启用线上模型推理，
也不把本作品集 Demo 表述为生产服务。
"""

APP_TEXT = '''"""Hugging Face Spaces entrypoint for ProcureGuard AI Demo."""

from __future__ import annotations

from demo.app import build_app


app = build_app()


if __name__ == "__main__":
    app.launch(share=False)
'''

REQUIREMENTS_TEXT = """gradio==5.50.0
pydantic>=2.0,<3.0
"""

ALLOWLIST_FILES = [
    "demo/__init__.py",
    "demo/app.py",
    "demo/demo_service.py",
    "demo/e2e_case_view.py",
    "demo/invoice_case_view.py",
    "demo/invoice_cases.json",
    "demo/scenario_registry.py",
    "demo/model_lab_view.py",
    "demo/architecture_view.py",
    "tests/fixtures/phase3h_demo_cases.json",
]

ALLOWLIST_DIRS = [
    "demo/assets/cases",
    "demo/e2e_cases",
    "demo/model_lab",
    "procureguard/db",
    "procureguard/models",
    "procureguard/phase3/explanation",
    "procureguard/productization",
    "procureguard/repositories",
    "procureguard/services",
    "procureguard/tools",
]

EXTRA_PACKAGE_FILES = [
    "procureguard/__init__.py",
    "procureguard/phase3/__init__.py",
    "procureguard/phase3/dataset.py",
    "procureguard/phase3/schemas.py",
]

FORBIDDEN_NAMES = {
    ".venv",
    ".venv-phase3",
    "artifacts",
    "checkpoints",
    "adapter",
    "__pycache__",
    ".pytest_cache",
    "notebooks",
}

FORBIDDEN_SUFFIXES = {
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".ipynb",
    ".sqlite",
    ".sqlite3",
    ".db",
}

FORBIDDEN_PATH_PARTS = {
    "requirements/phase3-lora.txt",
    "scripts/phase1",
    "scripts/phase3",
    "procureguard/extraction",
    "procureguard/api",
    "reports",
    "data/phase1",
}


def build_package() -> dict[str, Any]:
    """按 allowlist 重建发布目录并返回摘要。"""

    if SPACE_ROOT.exists():
        _remove_tree(SPACE_ROOT)
    SPACE_ROOT.mkdir(parents=True)

    copied: list[str] = []
    rejected: list[str] = []
    generated: list[str] = []

    _write_text(SPACE_ROOT / "README.md", README_TEXT)
    _write_text(SPACE_ROOT / "app.py", APP_TEXT)
    _write_text(SPACE_ROOT / "requirements.txt", REQUIREMENTS_TEXT)
    generated.extend(["README.md", "app.py", "requirements.txt"])

    for relative in [*ALLOWLIST_FILES, *EXTRA_PACKAGE_FILES]:
        _copy_file(relative, copied)

    for relative_dir in ALLOWLIST_DIRS:
        source_dir = PROJECT_ROOT / relative_dir
        for source in source_dir.rglob("*"):
            if source.is_file() and not _has_forbidden_part(source):
                relative = source.relative_to(PROJECT_ROOT).as_posix()
                _copy_file(relative, copied)

    rejected = _scan_rejected()
    forbidden_hits = _scan_forbidden_hits()
    package_size_bytes = sum(
        path.stat().st_size for path in SPACE_ROOT.rglob("*") if path.is_file()
    )
    required_files = ["README.md", "app.py", "requirements.txt"]
    missing_required = [
        item for item in required_files if not (SPACE_ROOT / item).exists()
    ]
    errors = []
    if forbidden_hits:
        errors.append("forbidden_files_present")
    if missing_required:
        errors.append("required_files_missing")

    return {
        "ready": not errors,
        "space_root": str(SPACE_ROOT),
        "generated_files": generated,
        "copied_files": sorted(copied),
        "rejected_files": rejected,
        "forbidden_hits": forbidden_hits,
        "contains_model_weights": any(
            hit.endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt"))
            for hit in forbidden_hits
        ),
        "contains_database": any(
            hit.endswith((".sqlite", ".sqlite3", ".db")) for hit in forbidden_hits
        ),
        "contains_notebook": any(hit.endswith(".ipynb") for hit in forbidden_hits),
        "package_size_bytes": package_size_bytes,
        "missing_required_files": missing_required,
        "errors": errors,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _remove_tree(path: Path) -> None:
    """删除旧 Space 包，兼容 Windows 下只读或短暂占用文件。"""

    def onerror(func: Any, failed_path: str, _exc_info: Any) -> None:
        try:
            os.chmod(failed_path, stat.S_IWRITE)
            func(failed_path)
        except PermissionError:
            time.sleep(0.2)
            func(failed_path)

    shutil.rmtree(path, onerror=onerror)


def _copy_file(relative: str, copied: list[str]) -> None:
    source = PROJECT_ROOT / relative
    target = SPACE_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() in {".py", ".md", ".json", ".txt", ".sql"}:
        text = source.read_text(encoding="utf-8")
        target.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    else:
        shutil.copy2(source, target)
    copied.append(relative)


def _scan_rejected() -> list[str]:
    categories = [
        ".cache/",
        ".venv/",
        "artifacts/",
        "checkpoints/",
        "notebooks/",
        "procureguard/extraction/",
        "reports/",
        "scripts/phase1/",
        "scripts/phase3/",
    ]
    return [item for item in categories if (PROJECT_ROOT / item).exists()]


def _scan_forbidden_hits() -> list[str]:
    hits: list[str] = []
    for path in SPACE_ROOT.rglob("*"):
        relative = path.relative_to(SPACE_ROOT).as_posix()
        parts = set(path.parts)
        if any(name in parts for name in FORBIDDEN_NAMES):
            hits.append(relative)
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            hits.append(relative)
            continue
        if any(relative.startswith(part) for part in FORBIDDEN_PATH_PARTS):
            hits.append(relative)
    return sorted(hits)


def _has_forbidden_part(path: Path) -> bool:
    return any(part in FORBIDDEN_NAMES for part in path.parts)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = build_package()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
