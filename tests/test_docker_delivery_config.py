"""Docker Compose 本地交付静态配置测试。"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_is_cpu_only_and_uses_demo_extra() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11-slim" in dockerfile
    assert 'python -m pip install ".[demo]"' in dockerfile
    assert "langchain" not in dockerfile.lower()
    assert "torch" not in dockerfile.lower()
    assert "transformers" not in dockerfile.lower()
    assert "cuda" not in dockerfile.lower()
    assert "COPY . ." not in dockerfile


def test_compose_defines_api_demo_ports_and_healthcheck() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  api:" in compose
    assert "  demo:" in compose
    assert '"8000:8000"' in compose
    assert '"7860:7860"' in compose
    assert "procureguard.api.main:app" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "server_name='0.0.0.0'" in compose
    assert "share=False" in compose
    assert "procureguard-runtime:/app/runtime" in compose


def test_compose_has_no_gpu_model_or_secret_configuration() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8").lower()

    for forbidden in (
        "nvidia",
        "cuda",
        "gpu",
        "hf_token",
        "huggingface_token",
        "openai_api_key",
        "phase3_model_dir",
        "phase3_adapter_dir",
    ):
        assert forbidden not in compose


def test_dockerignore_excludes_heavy_and_local_assets() -> None:
    ignored = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    for required in (
        ".git",
        ".venv",
        "artifacts",
        "checkpoints",
        "models_cache",
        "notebooks",
        "reports",
        "spaces",
        "*.safetensors",
    ):
        assert required in ignored


def test_delivery_document_records_runtime_not_verified() -> None:
    document = (PROJECT_ROOT / "docs" / "ENGINEERING_DELIVERY.md").read_text(encoding="utf-8")

    assert "configuration_ready=true" in document
    assert "runtime_not_verified=true" in document
    assert "这不是容器运行 PASS" in document
