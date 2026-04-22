from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from doc_check.persistence.repositories import ArtifactRepository
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_retention_cleanup_removes_artifact_files_and_expires_download(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        upload_response = client.post(
            "/reviews/upload",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        review_service = client.app.state.review_service
        repository = ArtifactRepository(config.database_path)
        artifact = review_service.get_artifact(_artifact_id_from_page(upload_response.text))
        expired_record = replace(
            artifact,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        repository.update(expired_record)

        cleanup_response = client.post("/maintenance/cleanup")
        download_response = client.get(f"/reviews/{artifact.artifact_id}/annotated")

    assert cleanup_response.status_code == 200
    assert "已清理 1 个过期工件" in cleanup_response.text
    assert not artifact.storage_path.parent.exists()
    assert download_response.status_code == 410


def _artifact_id_from_page(html: str) -> str:
    marker = "工件 ID："
    start = html.index(marker) + len(marker)
    return html[start:start + 32]
