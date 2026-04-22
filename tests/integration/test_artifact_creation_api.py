from __future__ import annotations

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from doc_check.persistence.repositories import ArtifactRepository
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_create_check_executes_review_and_returns_summary_metadata(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    DOCX_CONTENT_TYPE,
                )
            },
            data={"ruleset_id": "aeos", "ruleset_version": "2026.05"},
            headers={"x-forwarded-user": "reviewer@example.com"},
        )

    assert response.status_code == 201
    payload = response.json()
    artifact = payload["artifact"]
    artifact_id = artifact["artifact_id"]

    assert artifact["original_filename"] == "policy.docx"
    assert artifact["ruleset_id"] == "aeos"
    assert artifact["ruleset_version"] == "2026.05"
    assert artifact["status"] == "completed"
    assert artifact["created_by"] == "reviewer@example.com"
    assert artifact["auth_source"] == "x-forwarded-user"
    assert payload["summary"]["total_findings"] == 17
    assert payload["summary"]["pending_count"] == 17
    assert payload["links"]["review_page"] == f"/reviews/{artifact_id}"
    assert payload["links"]["annotated_docx"] == f"/reviews/{artifact_id}/annotated"
    assert len(payload["findings"]) == 17

    stored_path = config.artifacts_dir / artifact_id / "original.docx"
    assert stored_path.exists()
    assert stored_path.read_bytes() == fixture_paths["format_errors"].read_bytes()

    repository = ArtifactRepository(config.database_path)
    saved_record = repository.get(artifact_id)

    assert saved_record is not None
    assert saved_record.original_filename == "policy.docx"
    assert saved_record.created_by == "reviewer@example.com"
    assert saved_record.status.value == "completed"
    assert saved_record.annotated_path is not None and saved_record.annotated_path.exists()
    assert saved_record.summary_path is not None and saved_record.summary_path.exists()


def test_create_check_uses_local_identity_when_no_auth_header_is_present(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    DOCX_CONTENT_TYPE,
                )
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["artifact"]["created_by"] == "local"
    assert payload["artifact"]["auth_source"] == "local"
    assert payload["artifact"]["status"] == "completed"


def test_create_check_rejects_non_docx_uploads(tmp_path):
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/checks",
            files={"file": ("policy.pdf", b"not-docx", "application/pdf")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .docx uploads are supported"
