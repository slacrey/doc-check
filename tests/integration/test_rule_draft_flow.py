from __future__ import annotations

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from doc_check.domain.rule_drafts import RuleDraftStatus
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_rule_draft_detail_page_lists_uploaded_sources(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        create_response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        task_id = create_response.headers["location"].split("=", 1)[1]
        upload_response = client.post(
            f"/rule-drafts/{task_id}/sources",
            data={"source_type": "template"},
            files={
                "file": (
                    "template.docx",
                    fixture_paths["valid"].read_bytes(),
                    DOCX_CONTENT_TYPE,
                )
            },
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        detail_response = client.get(
            f"/rule-drafts/{task_id}",
            headers={"x-forwarded-user": "admin@example.com"},
        )

    assert upload_response.status_code == 303
    assert upload_response.headers["location"] == f"/rule-drafts/{task_id}"
    assert detail_response.status_code == 200
    assert "template.docx" in detail_response.text
    assert "template" in detail_response.text

    sources = app.state.rule_draft_repository.list_sources(task_id)
    assert len(sources) == 1
    assert sources[0].normalized_path is not None and sources[0].normalized_path.exists()


def test_rule_draft_source_upload_rejects_non_docx_files(tmp_path):
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        create_response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        task_id = create_response.headers["location"].split("=", 1)[1]
        response = client.post(
            f"/rule-drafts/{task_id}/sources",
            data={"source_type": "standard"},
            files={"file": ("spec.pdf", b"not-docx", "application/pdf")},
            headers={"x-forwarded-user": "admin@example.com"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .docx uploads are supported"


def test_rule_draft_generate_writes_loadable_pack(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        create_response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        task_id = create_response.headers["location"].split("=", 1)[1]
        for source_type, key in (("standard", "aeos_standard"), ("template", "valid")):
            upload_response = client.post(
                f"/rule-drafts/{task_id}/sources",
                data={"source_type": source_type},
                files={
                    "file": (
                        fixture_paths[key].name,
                        fixture_paths[key].read_bytes(),
                        DOCX_CONTENT_TYPE,
                    )
                },
                headers={"x-forwarded-user": "admin@example.com"},
                follow_redirects=False,
            )
            assert upload_response.status_code == 303

        response = client.post(
            f"/rule-drafts/{task_id}/generate",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        detail_response = client.get(
            f"/rule-drafts/{task_id}",
            headers={"x-forwarded-user": "admin@example.com"},
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/rule-drafts/{task_id}"
    assert detail_response.status_code == 200
    assert "证据摘要" in detail_response.text
    assert "输入来源：正式规范 1 份，标准模板 1 份，样本文档 0 份。" in detail_response.text
    assert "evidence.json（证据详情）" in detail_response.text

    task = app.state.rule_draft_repository.get_task(task_id)
    generated_root = task.output_dir / "generated"
    version_dirs = sorted(path for path in generated_root.iterdir() if path.is_dir())

    assert version_dirs
    rule_pack = load_rule_pack(version_dirs[-1])
    assert rule_pack.ruleset_id == "aeos"
    assert rule_pack.version
    assert any(rule.variant == "网络安全" for rule in rule_pack.preferred_terms)
    assert any(rule.term == "黑名单" for rule in rule_pack.banned_terms)


def test_rule_draft_exclude_source_and_regenerate_keeps_version_history(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        create_response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        task_id = create_response.headers["location"].split("=", 1)[1]

        for source_type, key in (("standard", "aeos_standard"), ("template", "valid")):
            upload_response = client.post(
                f"/rule-drafts/{task_id}/sources",
                data={"source_type": source_type},
                files={
                    "file": (
                        fixture_paths[key].name,
                        fixture_paths[key].read_bytes(),
                        DOCX_CONTENT_TYPE,
                    )
                },
                headers={"x-forwarded-user": "admin@example.com"},
                follow_redirects=False,
            )
            assert upload_response.status_code == 303

        first_generate_response = client.post(
            f"/rule-drafts/{task_id}/generate",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        assert first_generate_response.status_code == 303

        template_source = next(
            source
            for source in app.state.rule_draft_repository.list_sources(task_id)
            if source.original_filename == fixture_paths["valid"].name
        )
        exclude_response = client.post(
            f"/rule-drafts/{task_id}/sources/{template_source.source_id}/exclude",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        second_generate_response = client.post(
            f"/rule-drafts/{task_id}/generate",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        detail_response = client.get(
            f"/rule-drafts/{task_id}",
            headers={"x-forwarded-user": "admin@example.com"},
        )

    assert exclude_response.status_code == 303
    assert second_generate_response.status_code == 303
    assert detail_response.status_code == 200
    assert "已排除" in detail_response.text
    assert "差异摘要" in detail_response.text
    assert "必备标题新增 1 项，移除 2 项" in detail_response.text

    task = app.state.rule_draft_repository.get_task(task_id)
    generated_root = task.output_dir / "generated"
    version_dirs = sorted(path for path in generated_root.iterdir() if path.is_dir())
    assert len(version_dirs) == 2
    assert app.state.rule_draft_repository.list_sources(task_id)[1].is_excluded is True


def test_rule_draft_failed_generation_preserves_sources_and_allows_retry(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        create_response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        task_id = create_response.headers["location"].split("=", 1)[1]

        upload_response = client.post(
            f"/rule-drafts/{task_id}/sources",
            data={"source_type": "template"},
            files={
                "file": (
                    fixture_paths["valid"].name,
                    fixture_paths["valid"].read_bytes(),
                    DOCX_CONTENT_TYPE,
                )
            },
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        assert upload_response.status_code == 303

        template_source = app.state.rule_draft_repository.list_sources(task_id)[0]
        exclude_response = client.post(
            f"/rule-drafts/{task_id}/sources/{template_source.source_id}/exclude",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        failed_generate_response = client.post(
            f"/rule-drafts/{task_id}/generate",
            headers={"x-forwarded-user": "admin@example.com"},
        )
        failed_detail_response = client.get(
            f"/rule-drafts/{task_id}",
            headers={"x-forwarded-user": "admin@example.com"},
        )

        include_response = client.post(
            f"/rule-drafts/{task_id}/sources/{template_source.source_id}/include",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        retry_generate_response = client.post(
            f"/rule-drafts/{task_id}/generate",
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )
        completed_detail_response = client.get(
            f"/rule-drafts/{task_id}",
            headers={"x-forwarded-user": "admin@example.com"},
        )

    assert exclude_response.status_code == 303
    assert failed_generate_response.status_code == 400
    assert failed_generate_response.json()["detail"] == "No normalized sources are available for derivation"
    assert failed_detail_response.status_code == 200
    assert "failed" in failed_detail_response.text
    assert fixture_paths["valid"].name in failed_detail_response.text
    assert "已排除" in failed_detail_response.text

    assert include_response.status_code == 303
    assert retry_generate_response.status_code == 303
    assert completed_detail_response.status_code == 200
    assert "completed" in completed_detail_response.text
    assert "参与生成" in completed_detail_response.text

    task = app.state.rule_draft_repository.get_task(task_id)
    assert task is not None
    assert task.status is RuleDraftStatus.COMPLETED
