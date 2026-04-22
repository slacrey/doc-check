from __future__ import annotations

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from tests.support.app_config import make_test_config


def test_upload_page_shows_rule_draft_link_for_local_default_admin(tmp_path):
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "/rule-drafts" in response.text
    assert "规则草案生成" in response.text


def test_upload_page_hides_rule_draft_link_for_non_admin(tmp_path):
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "/rule-drafts" not in response.text


def test_upload_page_shows_rule_draft_link_for_admin(tmp_path):
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/", headers={"x-forwarded-user": "admin@example.com"})

    assert response.status_code == 200
    assert "/rule-drafts" in response.text
    assert "规则草案生成" in response.text


def test_rule_draft_page_requires_admin(tmp_path):
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/rule-drafts")

    assert response.status_code == 403


def test_local_admin_can_access_rule_draft_page_without_auth_header(tmp_path):
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/rule-drafts")

    assert response.status_code == 200
    assert "AEOS 规则草案生成" in response.text


def test_admin_can_create_empty_rule_draft_task(tmp_path):
    config = make_test_config(tmp_path, {"DOC_CHECK_ADMIN_USERS": "admin@example.com"})
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/rule-drafts",
            data={"ruleset_id": "aeos"},
            headers={"x-forwarded-user": "admin@example.com"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/rule-drafts?created_task_id=")

    tasks = app.state.rule_draft_repository.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].ruleset_id == "aeos"
    assert tasks[0].created_by == "admin@example.com"
