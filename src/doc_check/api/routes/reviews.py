from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from doc_check.api.routes.checks import (
    get_app_config,
    get_check_service,
    resolve_user_context,
)
from doc_check.config import AppConfig
from doc_check.domain.documents import CreateArtifactCommand
from doc_check.domain.findings import ReviewEntry, ReviewStatus
from doc_check.services.check_pipeline import ArtifactValidationError, CheckPipelineService
from doc_check.services.review_service import (
    ReviewExpiredError,
    ReviewNotFoundError,
    ReviewService,
    ReviewServiceError,
)
from doc_check.web.rendering import render_html_template

router = APIRouter(tags=["reviews"])


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


@router.get("/", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    config: AppConfig = Depends(get_app_config),
) -> HTMLResponse:
    cleanup_count = request.query_params.get("cleanup_count")
    message_html = ""
    if cleanup_count is not None:
        message_html = (
            f'<div class="message">已清理 {escape(cleanup_count)} 个过期工件。</div>'
        )

    html = render_html_template(
        config.templates_dir,
        "upload.html",
        message_html=message_html,
    )
    return HTMLResponse(html)


@router.post("/reviews/upload")
async def upload_for_review(
    request: Request,
    file: UploadFile = File(...),
    ruleset_id: str = Form("aeos"),
    ruleset_version: str = Form("2026.04"),
    config: AppConfig = Depends(get_app_config),
    check_service: CheckPipelineService = Depends(get_check_service),
    review_service: ReviewService = Depends(get_review_service),
):
    payload = await file.read()
    user = resolve_user_context(request, config)

    try:
        artifact = check_service.create_artifact(
            CreateArtifactCommand(
                original_filename=file.filename or "",
                content_type=file.content_type or "application/octet-stream",
                payload=payload,
                ruleset_id=ruleset_id,
                ruleset_version=ruleset_version,
                user=user,
            )
        )
        review_service.process_artifact(artifact.artifact_id)
    except ArtifactValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/reviews/{artifact.artifact_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/reviews/{artifact_id}", response_class=HTMLResponse)
async def review_page(
    artifact_id: str,
    config: AppConfig = Depends(get_app_config),
    review_service: ReviewService = Depends(get_review_service),
) -> HTMLResponse:
    try:
        session = review_service.load_review_session(artifact_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except ReviewServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    artifact = review_service.get_artifact(artifact_id)
    rows_html = "\n".join(_render_review_row(artifact_id, entry) for entry in session.review_entries)
    false_positive_count = sum(
        1 for entry in session.review_entries if entry.review_status is ReviewStatus.FALSE_POSITIVE
    )
    acceptable_exception_count = sum(
        1 for entry in session.review_entries if entry.review_status is ReviewStatus.ACCEPTABLE_EXCEPTION
    )

    html = render_html_template(
        config.templates_dir,
        "review.html",
        artifact_id=artifact.artifact_id,
        original_filename=escape(artifact.original_filename),
        ruleset_id=escape(artifact.ruleset_id),
        ruleset_version=escape(artifact.ruleset_version),
        artifact_status=escape(artifact.status.value),
        total_findings=session.summary_report.total_findings,
        pending_count=session.pending_count,
        false_positive_count=false_positive_count,
        acceptable_exception_count=acceptable_exception_count,
        rows_html=rows_html,
    )
    return HTMLResponse(html)


@router.post("/reviews/{artifact_id}/findings/{finding_id}")
async def update_review_finding(
    artifact_id: str,
    finding_id: str,
    request: Request,
    review_status: str = Form(...),
    config: AppConfig = Depends(get_app_config),
    review_service: ReviewService = Depends(get_review_service),
):
    user = resolve_user_context(request, config)
    try:
        review_service.update_review_state(
            artifact_id=artifact_id,
            finding_id=finding_id,
            status=ReviewStatus(review_status),
            actor=user.user_id,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except (ReviewServiceError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/reviews/{artifact_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/reviews/{artifact_id}/annotated")
async def download_annotated_docx(
    artifact_id: str,
    review_service: ReviewService = Depends(get_review_service),
):
    try:
        session = review_service.load_review_session(artifact_id)
    except ReviewNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReviewExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc

    if session.annotated_download_path is None or not session.annotated_download_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotated document for {artifact_id} is unavailable",
        )

    return FileResponse(
        session.annotated_download_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{artifact_id}-annotated.docx",
    )


@router.post("/maintenance/cleanup")
async def cleanup_expired_artifacts(
    review_service: ReviewService = Depends(get_review_service),
):
    cleaned = review_service.cleanup_expired_artifacts()
    return RedirectResponse(
        url=f"/?cleanup_count={len(cleaned)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _render_review_row(artifact_id: str, review_entry: ReviewEntry) -> str:
    entry = review_entry.summary_entry
    severity_badge = _badge_html(entry.severity, entry.severity)
    review_badge = _badge_html(review_entry.review_status.value, review_entry.review_status.value)
    suggestion_html = escape(entry.suggestion) if entry.suggestion else "—"
    evidence_html = f"<div><small>证据：{escape(entry.evidence)}</small></div>" if entry.evidence else ""
    target_html = "已写入批注" if entry.target.value == "commentable" else "仅摘要"

    return f"""
    <tr>
      <td>{severity_badge}<div><small>{escape(entry.category)}</small></div></td>
      <td>{escape(entry.location_label)}<div><small>{target_html}</small></div></td>
      <td>{escape(entry.message)}{evidence_html}</td>
      <td>{suggestion_html}</td>
      <td>{review_badge}</td>
      <td class="actions">
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.OPEN, "保持原判", "secondary")}
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.FALSE_POSITIVE, "标记误报", "ghost")}
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.ACCEPTABLE_EXCEPTION, "可接受例外", "secondary")}
      </td>
    </tr>
    """


def _review_action_form(
    artifact_id: str,
    finding_id: str,
    review_status: ReviewStatus,
    label: str,
    button_class: str,
) -> str:
    return f"""
    <form method="post" action="/reviews/{escape(artifact_id)}/findings/{escape(finding_id)}">
      <input type="hidden" name="review_status" value="{review_status.value}" />
      <button type="submit" class="{button_class}">{escape(label)}</button>
    </form>
    """


def _badge_html(label: str, css_class: str) -> str:
    return f'<span class="badge {escape(css_class)}">{escape(label)}</span>'
