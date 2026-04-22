from __future__ import annotations

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
