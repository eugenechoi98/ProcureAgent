"""FastAPI 应用入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from procureguard.api.dependencies import initialize_app_database
from procureguard.api.routes import invoice, review
from procureguard.config import Settings, get_settings
from procureguard.phase3.explanation.orchestrator import RewriteProvider


def create_app(
    settings: Settings | None = None,
    *,
    explanation_rewrite_provider: RewriteProvider | None = None,
) -> FastAPI:
    """创建 FastAPI 应用，便于测试传入临时配置。"""

    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = app_settings
        app.state.explanation_rewrite_provider = explanation_rewrite_provider
        initialize_app_database(app_settings)
        yield

    app = FastAPI(title="ProcureGuard AI", lifespan=lifespan)
    app.include_router(invoice.router)
    app.include_router(review.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """服务健康检查。"""

        return {"status": "ok", "service": "procureguard"}

    return app


app = create_app()
