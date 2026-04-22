from __future__ import annotations

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from doc_check.config import AppConfig
from doc_check.persistence.repositories import ArtifactRepository


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_create_check_persists_artifact_and_returns_metadata(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={"file": ("policy.docx", b"fake-docx-payload", DOCX_CONTENT_TYPE)},
            data={"ruleset_id": "aeos", "ruleset_version": "2026.04"},
            headers={"x-forwarded-user": "reviewer@example.com"},
        )

    assert response.status_code == 201
    payload = response.json()
    artifact_id = payload["artifact_id"]

    assert payload["original_filename"] == "policy.docx"
    assert payload["ruleset_id"] == "aeos"
    assert payload["ruleset_version"] == "2026.04"
    assert payload["status"] == "uploaded"
    assert payload["created_by"] == "reviewer@example.com"
    assert payload["auth_source"] == "x-forwarded-user"

    stored_path = config.artifacts_dir / artifact_id / "original.docx"
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"fake-docx-payload"

    repository = ArtifactRepository(config.database_path)
    saved_record = repository.get(artifact_id)

    assert saved_record is not None
    assert saved_record.original_filename == "policy.docx"
    assert saved_record.created_by == "reviewer@example.com"


def test_create_check_uses_local_identity_when_no_auth_header_is_present(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={"file": ("policy.docx", b"fake-docx-payload", DOCX_CONTENT_TYPE)},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_by"] == "local"
    assert payload["auth_source"] == "local"


def test_create_check_rejects_non_docx_uploads(tmp_path):
    config = AppConfig.from_env({}, cwd=tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={"file": ("policy.pdf", b"not-docx", "application/pdf")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .docx uploads are supported"
