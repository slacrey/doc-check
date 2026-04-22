from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from doc_check.api.routes.checks import get_app_config, is_admin_user, resolve_user_context
from doc_check.config import AppConfig
from doc_check.domain.rule_drafts import RuleDraftStatus, RuleDraftTask
from doc_check.persistence.repositories import RuleDraftRepository
from doc_check.rules.rule_pack import RulePackError, load_rule_pack
from doc_check.services.rule_derivation import RuleDerivationService
from doc_check.services.rule_draft_catalog import RuleDraftCatalogService
from doc_check.services.rule_draft_pipeline import RuleDraftPipelineError, RuleDraftPipelineService
from doc_check.services.rule_pack_writer import RulePackWriter
from doc_check.web.rendering import render_html_template

router = APIRouter(tags=["rule_drafts"])


def get_rule_draft_repository(request: Request) -> RuleDraftRepository:
    return request.app.state.rule_draft_repository


def get_rule_draft_pipeline_service(request: Request) -> RuleDraftPipelineService:
    return request.app.state.rule_draft_pipeline_service


def get_rule_derivation_service(request: Request) -> RuleDerivationService:
    return request.app.state.rule_derivation_service


def get_rule_draft_catalog_service(request: Request) -> RuleDraftCatalogService:
    return request.app.state.rule_draft_catalog_service


def get_rule_pack_writer(request: Request) -> RulePackWriter:
    return request.app.state.rule_pack_writer


def require_admin_user(request: Request, config: AppConfig):
    user = resolve_user_context(request, config)
    if not is_admin_user(user, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rule draft management requires admin access",
        )
    return user


@router.get("/rule-drafts", response_class=HTMLResponse)
async def rule_draft_page(
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
) -> HTMLResponse:
    user = require_admin_user(request, config)
    created_task_id = request.query_params.get("created_task_id")
    message_html = ""
    if created_task_id:
        message_html = (
            f'<div class="message">已创建草案任务：{escape(created_task_id)}</div>'
        )

    rows_html = "\n".join(_render_rule_draft_row(task) for task in repository.list_tasks())
    if not rows_html:
        rows_html = '<tr><td colspan="5">暂无草案任务。</td></tr>'

    html = render_html_template(
        config.templates_dir,
        "rule_draft_upload.html",
        message_html=message_html,
        current_user=escape(user.user_id),
        rows_html=rows_html,
    )
    return HTMLResponse(html)


@router.get("/rule-drafts/{task_id}", response_class=HTMLResponse)
async def rule_draft_detail_page(
    task_id: str,
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
    catalog_service: RuleDraftCatalogService = Depends(get_rule_draft_catalog_service),
) -> HTMLResponse:
    require_admin_user(request, config)
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft task: {task_id}")

    rows_html = "\n".join(_render_rule_draft_source_row(source) for source in repository.list_sources(task_id))
    if not rows_html:
        rows_html = '<tr><td colspan="8">暂无来源文件。</td></tr>'
    generated_versions_html = _render_generated_versions(
        task_id=task.task_id,
        versions=catalog_service.list_generated_versions(task=task, rulesets_dir=config.rulesets_dir),
    )

    html = render_html_template(
        config.templates_dir,
        "rule_draft_detail.html",
        task_id=escape(task.task_id),
        ruleset_id=escape(task.ruleset_id),
        status_label=escape(task.status.value),
        created_by=escape(task.created_by),
        created_at=escape(task.created_at.isoformat()),
        rows_html=rows_html,
        generated_versions_html=generated_versions_html,
    )
    return HTMLResponse(html)


@router.post("/rule-drafts")
async def create_rule_draft_task(
    request: Request,
    ruleset_id: str = Form("aeos"),
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
):
    user = require_admin_user(request, config)
    normalized_ruleset_id = ruleset_id.strip()
    if normalized_ruleset_id != "aeos":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only the AEOS ruleset draft flow is available",
        )

    task_id = uuid4().hex
    output_dir = config.rule_drafts_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=False)
    task = RuleDraftTask(
        task_id=task_id,
        ruleset_id=normalized_ruleset_id,
        status=RuleDraftStatus.CREATED,
        created_at=datetime.now(timezone.utc),
        created_by=user.user_id,
        auth_source=user.auth_source,
        output_dir=output_dir,
    )
    repository.create_task(task)

    return RedirectResponse(
        url=f"/rule-drafts?created_task_id={task_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/rule-drafts/{task_id}/sources")
async def upload_rule_draft_source(
    task_id: str,
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form(...),
    config: AppConfig = Depends(get_app_config),
    pipeline_service: RuleDraftPipelineService = Depends(get_rule_draft_pipeline_service),
):
    require_admin_user(request, config)
    payload = await file.read()
    try:
        pipeline_service.add_source(
            task_id=task_id,
            source_type=source_type,
            original_filename=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            payload=payload,
        )
    except RuleDraftPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/rule-drafts/{task_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/rule-drafts/{task_id}/sources/{source_id}/exclude")
async def exclude_rule_draft_source(
    task_id: str,
    source_id: str,
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
):
    require_admin_user(request, config)
    source = repository.update_source_exclusion(
        task_id=task_id,
        source_id=source_id,
        is_excluded=True,
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft source: {source_id}")
    return RedirectResponse(
        url=f"/rule-drafts/{task_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/rule-drafts/{task_id}/sources/{source_id}/include")
async def include_rule_draft_source(
    task_id: str,
    source_id: str,
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
):
    require_admin_user(request, config)
    source = repository.update_source_exclusion(
        task_id=task_id,
        source_id=source_id,
        is_excluded=False,
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft source: {source_id}")
    return RedirectResponse(
        url=f"/rule-drafts/{task_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/rule-drafts/{task_id}/generate")
async def generate_rule_draft_pack(
    task_id: str,
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
    derivation_service: RuleDerivationService = Depends(get_rule_derivation_service),
    pack_writer: RulePackWriter = Depends(get_rule_pack_writer),
):
    require_admin_user(request, config)
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft task: {task_id}")

    try:
        draft = derivation_service.derive(
            task=task,
            sources=tuple(repository.list_sources(task_id)),
            rulesets_dir=config.rulesets_dir,
        )
        version_dir = pack_writer.write(output_root=task.output_dir, draft=draft)
        load_rule_pack(version_dir)
        repository.update_task(
            RuleDraftTask(
                task_id=task.task_id,
                ruleset_id=task.ruleset_id,
                status=RuleDraftStatus.COMPLETED,
                created_at=task.created_at,
                created_by=task.created_by,
                auth_source=task.auth_source,
                output_dir=task.output_dir,
            )
        )
    except (ValueError, RulePackError) as exc:
        repository.update_task(
            RuleDraftTask(
                task_id=task.task_id,
                ruleset_id=task.ruleset_id,
                status=RuleDraftStatus.FAILED,
                created_at=task.created_at,
                created_by=task.created_by,
                auth_source=task.auth_source,
                output_dir=task.output_dir,
            )
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/rule-drafts/{task_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/rule-drafts/{task_id}/outputs/{version}/{filename}")
async def download_rule_draft_output(
    task_id: str,
    version: str,
    filename: str,
    request: Request,
    config: AppConfig = Depends(get_app_config),
    repository: RuleDraftRepository = Depends(get_rule_draft_repository),
):
    require_admin_user(request, config)
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft task: {task_id}")
    output_path = task.output_dir / "generated" / version / filename
    if not output_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown rule draft output: {filename}")
    return FileResponse(output_path, filename=f"{task_id}-{version}-{filename}")


def _render_rule_draft_row(task: RuleDraftTask) -> str:
    return f"""
    <tr>
      <td><a href="/rule-drafts/{escape(task.task_id)}"><code>{escape(task.task_id)}</code></a></td>
      <td>{escape(task.ruleset_id)}</td>
      <td>{escape(task.status.value)}</td>
      <td>{escape(task.created_by)}</td>
      <td>{escape(task.created_at.isoformat())}</td>
    </tr>
    """


def _render_rule_draft_source_row(source) -> str:
    normalized_label = "已生成快照" if source.normalized_path else "解析失败"
    parse_error_html = escape(source.parse_error) if source.parse_error else "—"
    participation_label = "已排除" if source.is_excluded else "参与生成"
    toggle_path = (
        f"/rule-drafts/{escape(source.task_id)}/sources/{escape(source.source_id)}/include"
        if source.is_excluded
        else f"/rule-drafts/{escape(source.task_id)}/sources/{escape(source.source_id)}/exclude"
    )
    toggle_label = "恢复参与生成" if source.is_excluded else "排除出生成范围"
    return f"""
    <tr>
      <td><code>{escape(source.source_id)}</code></td>
      <td>{escape(source.original_filename)}</td>
      <td>{escape(source.source_type.value)}</td>
      <td>{escape(source.uploaded_at.isoformat())}</td>
      <td>{participation_label}</td>
      <td>{normalized_label}</td>
      <td>{parse_error_html}</td>
      <td>
        <form method="post" action="{toggle_path}">
          <button type="submit">{toggle_label}</button>
        </form>
      </td>
    </tr>
    """


def _render_generated_versions(*, task_id: str, versions) -> str:
    if not versions:
        return "<p class=\"meta\">尚未生成草案规则包。</p>"

    sections: list[str] = []
    for version in versions:
        links = [
            f'<li><a href="/rule-drafts/{escape(task_id)}/outputs/{escape(version.version)}/{escape(filename)}">{escape(_render_output_filename(filename))}</a></li>'
            for filename in version.files
        ]
        badge_html = '<span class="badge latest">最新</span>' if version.is_latest else ""
        evidence_html = "".join(f"<li>{escape(line)}</li>" for line in version.evidence_summary_lines)
        diff_html = "".join(f"<li>{escape(line)}</li>" for line in version.diff_summary_lines)
        sections.append(
            f"""
    <div class="panel">
      <h3>{escape(version.version)} {badge_html}</h3>
      <p><strong>证据摘要</strong></p>
      <ul>
        {evidence_html}
      </ul>
      <p><strong>差异摘要</strong></p>
      <ul>
        {diff_html}
      </ul>
      <ul>
        {''.join(links)}
      </ul>
    </div>
            """
        )
    return "\n".join(sections)


def _render_output_filename(filename: str) -> str:
    if filename == "evidence.json":
        return "evidence.json（证据详情）"
    return filename
