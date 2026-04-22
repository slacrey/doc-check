from __future__ import annotations

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from tests.support.app_config import make_test_config


def test_rules_index_page_lists_supported_rulesets(tmp_path):
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/rules")

    assert response.status_code == 200
    assert "规则说明" in response.text
    assert "AEOS 制度文件" in response.text
    assert "新闻宣传稿" in response.text
    assert "发言稿" in response.text
    assert '/rules/aeos' in response.text


def test_ruleset_detail_page_renders_rule_table(tmp_path):
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.get("/rules/aeos")

    assert response.status_code == 200
    assert "规则依据与适用范围" in response.text
    assert "layout.page-width.a4" in response.text
    assert "punctuation.ascii-comma-cjk" in response.text
    assert "规则总数" in response.text
    assert 'id="layout-page-width-a4"' in response.text
