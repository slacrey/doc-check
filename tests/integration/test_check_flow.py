from __future__ import annotations

import re

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_upload_to_review_page_flow_renders_summary_and_download_link(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/reviews/upload",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert response.status_code == 200
    assert "检验结果" in response.text
    assert "总问题数" in response.text
    assert "待处理" in response.text
    assert "下载批注版文档" in response.text
    assert "查看该文种规则说明" in response.text
    assert '/rules/aeos#layout-page-width-a4' in response.text


def test_review_page_supports_category_filter(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/reviews/upload",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        artifact_match = re.search(r"/reviews/([a-f0-9]+)", response.text)
        assert artifact_match is not None
        artifact_id = artifact_match.group(1)

        filtered = client.get(f"/reviews/{artifact_id}?filter_category=terminology")

    assert filtered.status_code == 200
    assert "当前显示</span><strong>2</strong>" in filtered.text
    assert "发现非标准术语：网络安全" in filtered.text
    assert "文档中存在不建议直接使用的表述“黑名单”。" in filtered.text
    assert "页面宽度应符合 A4 纸规格" not in filtered.text
