"""GPU Notebook runtime context 与变量顺序测试。"""

import ast
import json
from pathlib import Path

import pytest

from procureguard.extraction.gpu_notebook_context import (
    GPU_NOTEBOOK_REQUIRED_NAMES,
    build_gpu_notebook_context,
    find_missing_runtime_names,
    require_complete_runtime_context,
)
from procureguard.extraction.schemas import SroieSample


NOTEBOOK_PATH = Path("notebooks/phase1_layoutlmv3_training.ipynb")
CRITICAL_NAMES = [
    "LABEL2ID",
    "ID2LABEL",
    "train_samples",
    "validation_samples",
    "processor",
    "train_dataset",
    "validation_dataset",
    "train_loader",
    "validation_loader",
    "torch",
    "device",
    "model",
    "optimizer",
    "scheduler",
    "move_batch",
    "validate_token_level",
]


class FakeCuda:
    """测试用 CUDA 接口。"""

    @staticmethod
    def is_available() -> bool:
        return False


class FakeTorch:
    """测试用最小 torch 模块。"""

    cuda = FakeCuda()

    @staticmethod
    def device(name: str) -> str:
        return name


class FakeProcessor:
    """不访问模型网络的 processor。"""


def write_processed_sample(path: Path, sample_id: str) -> None:
    """写入可由真实 loader 读取的单样本 JSONL。"""

    row = {
        "sample_id": sample_id,
        "image_path": str(path.parent / f"{sample_id}.jpg"),
        "tokens": [
            {"text": "ACME", "bbox": [0, 0, 100, 100], "confidence": 1.0}
        ],
        "labels": {
            "company": "ACME",
            "address": "",
            "date": "",
            "total": "",
        },
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


@pytest.fixture
def context_fixture(tmp_path: Path):
    """构造不依赖 GPU 和真实模型的 hydrate 输入。"""

    root = tmp_path / "ProcureAgent"
    processed = root / "data" / "phase1" / "sroie_task3" / "processed"
    model = tmp_path / "models" / "layoutlmv3-base"
    baseline = root / "reports" / "phase1" / "baseline.json"
    processed.mkdir(parents=True)
    model.mkdir(parents=True)
    baseline.parent.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    write_processed_sample(processed / "train.jsonl", "train-1")
    write_processed_sample(processed / "validation.jsonl", "validation-1")
    baseline.write_text(
        json.dumps(
            {
                "metrics": [
                    {"field": "company", "f1": 0.5},
                    {"field": "macro", "f1": 0.43872030739086737},
                ]
            }
        ),
        encoding="utf-8",
    )
    return root, processed, model, baseline


def build_fixture_context(context_fixture, calls: list[tuple[Path, bool]] | None = None):
    root, processed, model, baseline = context_fixture

    def fake_processor_factory(model_path, *, local_files_only):
        if calls is not None:
            calls.append((Path(model_path), local_files_only))
        return FakeProcessor()

    return build_gpu_notebook_context(
        project_root=root,
        processed_dir=processed,
        model_dir=model,
        baseline_report_path=baseline,
        processor_factory=fake_processor_factory,
        torch_module=FakeTorch(),
    )


def test_runtime_context_contains_all_required_names(context_fixture):
    context = build_fixture_context(context_fixture)

    assert find_missing_runtime_names(context) == []
    assert set(GPU_NOTEBOOK_REQUIRED_NAMES).issubset(context)


def test_bio_label_mapping_is_bidirectional_and_has_nine_labels(context_fixture):
    context = build_fixture_context(context_fixture)
    label2id = context["LABEL2ID"]
    id2label = context["ID2LABEL"]

    assert len(label2id) == 9
    assert len(id2label) == 9
    assert all(id2label[index] == label for label, index in label2id.items())


def test_context_uses_real_sroie_loader_and_baseline_f1(context_fixture):
    context = build_fixture_context(context_fixture)

    assert isinstance(context["train_samples"][0], SroieSample)
    assert isinstance(context["validation_samples"][0], SroieSample)
    assert context["BASELINE_MACRO_F1"] == pytest.approx(0.4387, abs=0.0001)


def test_missing_local_model_directory_stops_hydration(context_fixture):
    root, processed, model, baseline = context_fixture
    model.rmdir()

    with pytest.raises(FileNotFoundError, match="will not access Hugging Face"):
        build_gpu_notebook_context(
            project_root=root,
            processed_dir=processed,
            model_dir=model,
            baseline_report_path=baseline,
            processor_factory=lambda *args, **kwargs: FakeProcessor(),
            torch_module=FakeTorch(),
        )


def test_processor_is_forced_to_local_files_only(context_fixture):
    calls: list[tuple[Path, bool]] = []
    context = build_fixture_context(context_fixture, calls)

    assert isinstance(context["processor"], FakeProcessor)
    assert calls == [(context_fixture[2].resolve(), True)]
    assert context["MODEL_NAME"] == str(context_fixture[2].resolve())


def test_preflight_reports_all_missing_names_at_once():
    required = ["PROJECT_ROOT", "LABEL2ID", "processor"]
    namespace = {"PROJECT_ROOT": Path(".")}

    assert find_missing_runtime_names(namespace, required) == ["LABEL2ID", "processor"]
    with pytest.raises(RuntimeError, match=r"\['LABEL2ID', 'processor'\]"):
        require_complete_runtime_context(namespace, required)


def notebook_code_cells() -> list[str]:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    ]


def test_dataset_cell_executes_after_hydration_without_label_name_error(context_fixture):
    cells = notebook_code_cells()
    context = build_fixture_context(context_fixture)
    dataset_cell = next(source for source in cells if "train_dataset = " in source)

    exec(dataset_cell, context)

    assert len(context["train_dataset"]) == 1
    assert len(context["validation_dataset"]) == 1


def definitions_and_uses(source: str, names: set[str]) -> tuple[set[str], set[str]]:
    """提取单元格中的关键变量定义和读取。"""

    tree = ast.parse(source)
    definitions = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param))
    }
    definitions.update(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    uses = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names
    }
    return definitions & names, uses


def test_notebook_critical_variables_are_defined_before_use():
    cells = notebook_code_cells()
    hydrate_index = next(
        index for index, source in enumerate(cells, start=1)
        if "globals().update(context)" in source
    )
    defined: set[str] = set()
    first_definition: dict[str, int] = {}
    first_use: dict[str, int] = {}
    used_before_definition: dict[str, int] = {}

    for index, source in enumerate(cells, start=1):
        if index == hydrate_index:
            for name in GPU_NOTEBOOK_REQUIRED_NAMES:
                defined.add(name)
                first_definition.setdefault(name, index)
        cell_definitions, cell_uses = definitions_and_uses(source, set(CRITICAL_NAMES))
        for name in cell_uses:
            first_use.setdefault(name, index)
            if name not in defined and name not in cell_definitions:
                used_before_definition.setdefault(name, index)
        for name in cell_definitions:
            defined.add(name)
            first_definition.setdefault(name, index)

    assert used_before_definition == {}
    assert set(CRITICAL_NAMES).issubset(first_definition)
    assert all(
        first_definition[name] <= first_use.get(name, first_definition[name])
        for name in CRITICAL_NAMES
    )


def test_notebook_preflight_precedes_dataset_and_checks_all_required_names():
    cells = notebook_code_cells()
    hydrate_index = next(i for i, source in enumerate(cells) if "globals().update(context)" in source)
    preflight_index = next(i for i, source in enumerate(cells) if "missing_names =" in source)
    dataset_index = next(i for i, source in enumerate(cells) if "train_dataset = " in source)

    assert hydrate_index < preflight_index < dataset_index
    assert "GPU_NOTEBOOK_REQUIRED_NAMES" in cells[preflight_index]
    assert "LABEL2ID" not in cells[dataset_index].split("train_dataset =", 1)[0]
