from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from doc_check.api.routes.checks import (
    get_app_config,
    get_execution_service,
    is_admin_user,
    resolve_user_context,
)
from doc_check.config import AppConfig
from doc_check.domain.documents import CreateArtifactCommand
from doc_check.domain.findings import ReviewEntry, ReviewStatus
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import ArtifactValidationError
from doc_check.services.review_service import (
    ReviewExpiredError,
    ReviewNotFoundError,
    ReviewService,
    ReviewServiceError,
)
from doc_check.services.rule_catalog import (
    RulesetGuide,
    RulesetGuideNotFoundError,
    list_ruleset_guides,
    load_ruleset_guide,
)
from doc_check.web.rendering import render_html_template

router = APIRouter(tags=["reviews"])
REVIEW_STATUS_OPTIONS = tuple(status.value for status in ReviewStatus)


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


@router.get("/", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    config: AppConfig = Depends(get_app_config),
) -> HTMLResponse:
    user = resolve_user_context(request, config)
    cleanup_count = request.query_params.get("cleanup_count")
    message_html = ""
    if cleanup_count is not None:
        message_html = (
            f'<div class="message">已清理 {escape(cleanup_count)} 个过期工件。</div>'
        )
    management_panel_html = ""
    if is_admin_user(user, config):
        management_panel_html = """
    <div class="panel">
      <h2>管理入口</h2>
      <p class="meta">规则维护人可在此创建 AEOS 规则草案任务，后续再上传规范、模板和样本文档。</p>
      <div class="actions">
        <a href="/rule-drafts">规则草案生成</a>
      </div>
    </div>
        """

    guide_links_html = "\n".join(
        f'<li><a href="/rules/{escape(guide.ruleset_id)}">{escape(guide.document_type)}规则说明</a></li>'
        for guide in list_ruleset_guides(config.rulesets_dir)
    )

    html = render_html_template(
        config.templates_dir,
        "upload.html",
        message_html=message_html,
        guide_links_html=guide_links_html,
        management_panel_html=management_panel_html,
    )
    return HTMLResponse(html)


@router.post("/reviews/upload")
async def upload_for_review(
    request: Request,
    file: UploadFile = File(...),
    ruleset_id: str = Form("aeos"),
    ruleset_version: str = Form("2026.05"),
    config: AppConfig = Depends(get_app_config),
    execution_service: CheckExecutionService = Depends(get_execution_service),
):
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReviewServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return RedirectResponse(
        url=f"/reviews/{result.artifact_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/reviews/{artifact_id}", response_class=HTMLResponse)
async def review_page(
    artifact_id: str,
    request: Request,
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
    filter_severity = _normalize_filter_value(
        request.query_params.get("filter_severity"),
        session.summary_report.counts_by_severity.keys(),
    )
    filter_category = _normalize_filter_value(
        request.query_params.get("filter_category"),
        session.summary_report.counts_by_category.keys(),
    )
    filter_review_status = _normalize_filter_value(
        request.query_params.get("filter_review_status"),
        REVIEW_STATUS_OPTIONS,
    )
    active_filter_params = _build_filter_params(
        filter_severity=filter_severity,
        filter_category=filter_category,
        filter_review_status=filter_review_status,
    )
    filtered_entries = tuple(
        entry
        for entry in session.review_entries
        if _matches_review_filters(
            entry,
            filter_severity=filter_severity,
            filter_category=filter_category,
            filter_review_status=filter_review_status,
        )
    )
    rows_html = "\n".join(
        _render_review_row(
            artifact_id,
            artifact.ruleset_id,
            active_filter_params,
            entry,
        )
        for entry in filtered_entries
    )
    if not rows_html:
        rows_html = '<tr><td colspan="6">当前筛选条件下没有问题项。</td></tr>'
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
        ruleset_guide_path=f"/rules/{escape(artifact.ruleset_id)}",
        total_findings=session.summary_report.total_findings,
        filtered_findings=len(filtered_entries),
        pending_count=session.pending_count,
        false_positive_count=false_positive_count,
        acceptable_exception_count=acceptable_exception_count,
        filter_form_html=_render_filter_form(
            artifact_id=artifact.artifact_id,
            severity_counts=session.summary_report.counts_by_severity,
            category_counts=session.summary_report.counts_by_category,
            filter_severity=filter_severity,
            filter_category=filter_category,
            filter_review_status=filter_review_status,
        ),
        clear_filters_path=f"/reviews/{escape(artifact.artifact_id)}",
        rows_html=rows_html,
    )
    return HTMLResponse(html)


@router.post("/reviews/{artifact_id}/findings/{finding_id}")
async def update_review_finding(
    artifact_id: str,
    finding_id: str,
    request: Request,
    review_status: str = Form(...),
    filter_severity: str = Form(""),
    filter_category: str = Form(""),
    filter_review_status: str = Form(""),
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

    redirect_suffix = _build_query_suffix(
        _build_filter_params(
            filter_severity=filter_severity or None,
            filter_category=filter_category or None,
            filter_review_status=filter_review_status or None,
        )
    )
    return RedirectResponse(
        url=f"/reviews/{artifact_id}{redirect_suffix}",
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


@router.get("/rules", response_class=HTMLResponse)
async def rules_index_page(
    config: AppConfig = Depends(get_app_config),
) -> HTMLResponse:
    guides = list_ruleset_guides(config.rulesets_dir)
    cards_html = "\n".join(_render_ruleset_card(guide) for guide in guides)
    html = render_html_template(
        config.templates_dir,
        "rules_index.html",
        cards_html=cards_html,
    )
    return HTMLResponse(html)


@router.get("/rules/{ruleset_id}", response_class=HTMLResponse)
async def ruleset_detail_page(
    ruleset_id: str,
    config: AppConfig = Depends(get_app_config),
) -> HTMLResponse:
    try:
        guide = load_ruleset_guide(config.rulesets_dir, ruleset_id)
    except RulesetGuideNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    rows_html = "\n".join(_render_rule_guide_row(entry) for entry in guide.entries)
    category_counts_html = "".join(
        f'<span class="chip">{escape(label)} {count}</span>'
        for label, count in guide.category_counts
    )

    html = render_html_template(
        config.templates_dir,
        "ruleset_detail.html",
        ruleset_name=escape(guide.name),
        document_type=escape(guide.document_type),
        ruleset_id=escape(guide.ruleset_id),
        ruleset_version=escape(guide.version),
        category_counts_html=category_counts_html,
        basis_summary=escape(guide.note.basis_summary),
        scope_summary=escape(guide.note.scope_summary),
        limitation_summary=escape(guide.note.limitation_summary),
        total_rules=guide.total_rules,
        rows_html=rows_html,
    )
    return HTMLResponse(html)


def _render_review_row(
    artifact_id: str,
    ruleset_id: str,
    active_filter_params: dict[str, str],
    review_entry: ReviewEntry,
) -> str:
    entry = review_entry.summary_entry
    severity_badge = _badge_html(entry.severity, entry.severity)
    review_badge = _badge_html(review_entry.review_status.value, review_entry.review_status.value)
    suggestion_html = escape(entry.suggestion) if entry.suggestion else "—"
    evidence_html = f"<div><small>证据：{escape(entry.evidence)}</small></div>" if entry.evidence else ""
    target_html = "已写入批注" if entry.target.value == "commentable" else "仅摘要"
    rule_link_html = (
        f'<div><small>规则：<a href="/rules/{escape(ruleset_id)}#{_rule_anchor(entry.rule_id)}">'
        f'{escape(entry.rule_id)}</a></small></div>'
    )

    return f"""
    <tr>
      <td>{severity_badge}<div><small>{escape(entry.category)}</small></div></td>
      <td>{escape(entry.location_label)}<div><small>{target_html}</small></div></td>
      <td>{escape(entry.message)}{rule_link_html}{evidence_html}</td>
      <td>{suggestion_html}</td>
      <td>{review_badge}</td>
      <td class="actions">
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.OPEN, "保持原判", "secondary", active_filter_params)}
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.FALSE_POSITIVE, "标记误报", "ghost", active_filter_params)}
        {_review_action_form(artifact_id, entry.finding_id, ReviewStatus.ACCEPTABLE_EXCEPTION, "可接受例外", "secondary", active_filter_params)}
      </td>
    </tr>
    """


def _review_action_form(
    artifact_id: str,
    finding_id: str,
    review_status: ReviewStatus,
    label: str,
    button_class: str,
    active_filter_params: dict[str, str],
) -> str:
    hidden_filter_inputs = "".join(
        f'<input type="hidden" name="{escape(key)}" value="{escape(value)}" />'
        for key, value in active_filter_params.items()
    )
    return f"""
    <form method="post" action="/reviews/{escape(artifact_id)}/findings/{escape(finding_id)}">
      <input type="hidden" name="review_status" value="{review_status.value}" />
      {hidden_filter_inputs}
      <button type="submit" class="{button_class}">{escape(label)}</button>
    </form>
    """


def _badge_html(label: str, css_class: str) -> str:
    return f'<span class="badge {escape(css_class)}">{escape(label)}</span>'


def _render_ruleset_card(guide: RulesetGuide) -> str:
    chips_html = "".join(
        f'<span class="chip">{escape(label)} {count}</span>'
        for label, count in guide.category_counts
    )
    return f"""
    <div class="panel">
      <h2>{escape(guide.document_type)}</h2>
      <p class="meta">{escape(guide.name)}</p>
      <p class="meta">规则包版本：{escape(guide.version)}</p>
      <p>{escape(guide.note.scope_summary)}</p>
      <div class="chips">{chips_html}</div>
      <p class="link-line"><a href="/rules/{escape(guide.ruleset_id)}">查看规则明细</a></p>
    </div>
    """


def _render_rule_guide_row(entry) -> str:
    severity_badge = _badge_html(entry.severity, entry.severity)
    disposition_badge = _badge_html(entry.disposition, entry.disposition)
    suggestion_html = escape(entry.suggestion) if entry.suggestion else "—"
    return f"""
    <tr id="{_rule_anchor(entry.rule_id)}">
      <td>{escape(entry.category_label)}</td>
      <td>{escape(entry.scope_label)}</td>
      <td><code>{escape(entry.rule_id)}</code></td>
      <td>{escape(entry.message)}</td>
      <td>{suggestion_html}</td>
      <td>{severity_badge} {disposition_badge}</td>
    </tr>
    """


def _rule_anchor(rule_id: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in rule_id).strip("-")


def _matches_review_filters(
    review_entry: ReviewEntry,
    *,
    filter_severity: str | None,
    filter_category: str | None,
    filter_review_status: str | None,
) -> bool:
    if filter_severity is not None and review_entry.summary_entry.severity != filter_severity:
        return False
    if filter_category is not None and review_entry.summary_entry.category != filter_category:
        return False
    if filter_review_status is not None and review_entry.review_status.value != filter_review_status:
        return False
    return True


def _normalize_filter_value(raw_value: str | None, allowed_values) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        return None
    allowed = {str(value) for value in allowed_values}
    return normalized if normalized in allowed else None


def _build_filter_params(
    *,
    filter_severity: str | None,
    filter_category: str | None,
    filter_review_status: str | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    if filter_severity:
        params["filter_severity"] = filter_severity
    if filter_category:
        params["filter_category"] = filter_category
    if filter_review_status:
        params["filter_review_status"] = filter_review_status
    return params


def _build_query_suffix(params: dict[str, str]) -> str:
    if not params:
        return ""
    return f"?{urlencode(params)}"


def _render_filter_form(
    *,
    artifact_id: str,
    severity_counts: dict[str, int],
    category_counts: dict[str, int],
    filter_severity: str | None,
    filter_category: str | None,
    filter_review_status: str | None,
) -> str:
    severity_options = _render_select_options(
        label="全部级别",
        options=tuple(sorted(severity_counts.items())),
        selected=filter_severity,
    )
    category_options = _render_select_options(
        label="全部类别",
        options=tuple(sorted(category_counts.items())),
        selected=filter_category,
    )
    review_status_labels = {
        ReviewStatus.OPEN.value: "待处理",
        ReviewStatus.FALSE_POSITIVE.value: "已标误报",
        ReviewStatus.ACCEPTABLE_EXCEPTION.value: "可接受例外",
    }
    review_status_counts = {
        ReviewStatus.OPEN.value: None,
        ReviewStatus.FALSE_POSITIVE.value: None,
        ReviewStatus.ACCEPTABLE_EXCEPTION.value: None,
    }
    review_status_options = _render_select_options(
        label="全部状态",
        options=tuple(
            (value, review_status_counts[value], review_status_labels[value])
            for value in REVIEW_STATUS_OPTIONS
        ),
        selected=filter_review_status,
    )
    return f"""
    <form method="get" action="/reviews/{escape(artifact_id)}" class="filters">
      <label>级别
        <select name="filter_severity">{severity_options}</select>
      </label>
      <label>类别
        <select name="filter_category">{category_options}</select>
      </label>
      <label>状态
        <select name="filter_review_status">{review_status_options}</select>
      </label>
      <button type="submit">应用筛选</button>
    </form>
    """


def _render_select_options(
    *,
    label: str,
    options,
    selected: str | None,
) -> str:
    rendered = [f'<option value="">{escape(label)}</option>']
    for item in options:
        if len(item) == 2:
            value, count = item
            option_label = f"{value} ({count})"
        else:
            value, count, option_label = item
            if count is not None:
                option_label = f"{option_label} ({count})"
        selected_attr = ' selected="selected"' if selected == value else ""
        rendered.append(
            f'<option value="{escape(str(value))}"{selected_attr}>{escape(str(option_label))}</option>'
        )
    return "".join(rendered)
