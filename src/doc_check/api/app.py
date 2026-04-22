from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from doc_check.api.routes.checks import router as checks_router
from doc_check.api.routes.rule_drafts import router as rule_drafts_router
from doc_check.api.routes.reviews import router as reviews_router
from doc_check.config import AppConfig
from doc_check.persistence.repositories import ArtifactRepository, RuleDraftRepository
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import CheckPipelineService
from doc_check.services.rule_derivation import RuleDerivationService
from doc_check.services.rule_draft_catalog import RuleDraftCatalogService
from doc_check.services.rule_draft_pipeline import RuleDraftPipelineService
from doc_check.services.rule_pack_writer import RulePackWriter
from doc_check.services.review_service import ReviewService
from doc_check.services.source_normalizer import SourceNormalizer


def build_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or AppConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_config.ensure_directories()
        repository = ArtifactRepository(app_config.database_path)
        repository.init_schema()
        rule_draft_repository = RuleDraftRepository(app_config.database_path)
        rule_draft_repository.init_schema()

        app.state.config = app_config
        app.state.artifact_repository = repository
        app.state.rule_draft_repository = rule_draft_repository
        app.state.check_service = CheckPipelineService(
            config=app_config,
            repository=repository,
        )
        app.state.rule_draft_pipeline_service = RuleDraftPipelineService(
            config=app_config,
            repository=rule_draft_repository,
            source_normalizer=SourceNormalizer(),
        )
        app.state.rule_derivation_service = RuleDerivationService()
        app.state.rule_draft_catalog_service = RuleDraftCatalogService()
        app.state.rule_pack_writer = RulePackWriter()
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
    app.include_router(rule_drafts_router)
    app.include_router(reviews_router)

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app
