from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from doc_check.config import AppConfig
from doc_check.domain.documents import CreateArtifactCommand, UserContext
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import ArtifactValidationError
from doc_check.services.review_service import ReviewServiceError

router = APIRouter(tags=["checks"])


def get_app_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_execution_service(request: Request) -> CheckExecutionService:
    return request.app.state.execution_service


def resolve_user_context(request: Request, config: AppConfig) -> UserContext:
    for header_name in config.identity_headers:
        header_value = request.headers.get(header_name)
        if header_value:
            return UserContext(
                user_id=header_value,
                display_name=header_value,
                auth_source=header_name,
                is_authenticated=True,
            )

    return UserContext.local(config.local_user_id)


@router.post("/checks", status_code=status.HTTP_201_CREATED)
async def create_check(
    request: Request,
    file: UploadFile = File(...),
    ruleset_id: str = Form("aeos"),
    ruleset_version: str = Form("2026.05"),
    config: AppConfig = Depends(get_app_config),
    execution_service: CheckExecutionService = Depends(get_execution_service),
) -> dict[str, object]:
    payload = await file.read()
    user = resolve_user_context(request, config)

    try:
        result = execution_service.run_check(
            CreateArtifactCommand(
                original_filename=file.filename or "",
                content_type=file.content_type or "application/octet-stream",
                payload=payload,
                ruleset_id=ruleset_id,
                ruleset_version=ruleset_version,
                user=user,
            )
        )
    except ArtifactValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ReviewServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    response = result.as_public_dict()
    response["links"] = {
        "review_page": f"/reviews/{result.artifact_id}",
        "annotated_docx": f"/reviews/{result.artifact_id}/annotated",
    }
    return response
