from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from doc_check.api.routes.checks import router as checks_router
from doc_check.api.routes.reviews import router as reviews_router
from doc_check.config import AppConfig
from doc_check.persistence.repositories import ArtifactRepository
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import CheckPipelineService
from doc_check.services.review_service import ReviewService


def build_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or AppConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_config.ensure_directories()
        repository = ArtifactRepository(app_config.database_path)
        repository.init_schema()

        app.state.config = app_config
        app.state.artifact_repository = repository
        app.state.check_service = CheckPipelineService(
            config=app_config,
            repository=repository,
        )
        app.state.review_service = ReviewService(
            config=app_config,
            repository=repository,
        )
        app.state.execution_service = CheckExecutionService(
            check_service=app.state.check_service,
            review_service=app.state.review_service,
        )
        yield

    app = FastAPI(title="doc-check", lifespan=lifespan)
    app.include_router(checks_router)
    app.include_router(reviews_router)

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app
