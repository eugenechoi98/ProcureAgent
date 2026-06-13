# ProcureGuard AI CPU-only 本地交付镜像
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_ANALYTICS_ENABLED=False

WORKDIR /app

COPY pyproject.toml README.md ./
COPY procureguard ./procureguard
COPY demo ./demo
COPY tests/fixtures/phase3h_demo_cases.json ./tests/fixtures/phase3h_demo_cases.json

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[demo]"

EXPOSE 8000 7860

CMD ["python", "-m", "uvicorn", "procureguard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
