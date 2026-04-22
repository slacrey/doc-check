from __future__ import annotations

from pathlib import Path

from doc_check.domain.documents import CreateArtifactCommand, UserContext
from doc_check.persistence.repositories import ArtifactRepository
from doc_check.services.check_pipeline import CheckPipelineService
from doc_check.services.review_service import ReviewService, ReviewStatus
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_review_service_processes_artifact_and_persists_outputs(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    config.ensure_directories()
    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    check_service = CheckPipelineService(config=config, repository=repository)
    artifact = check_service.create_artifact(
        CreateArtifactCommand(
            original_filename="policy.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            payload=fixture_paths["format_errors"].read_bytes(),
            ruleset_id="aeos",
            ruleset_version="2026.04",
            user=UserContext.local("tester"),
        )
    )

    review_service = ReviewService(config=config, repository=repository)
    completed = review_service.process_artifact(artifact.artifact_id)
    session = review_service.load_review_session(artifact.artifact_id)

    assert completed.status.value == "completed"
    assert completed.annotated_path is not None and completed.annotated_path.exists()
    assert completed.summary_path is not None and completed.summary_path.exists()
    assert (artifact.storage_path.parent / "findings.json").exists()
    assert (artifact.storage_path.parent / "review_states.json").exists()
    assert session.summary_report.total_findings == 9
    assert session.pending_count == 9


def test_review_service_updates_finding_status_and_reduces_pending_count(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    config.ensure_directories()
    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    check_service = CheckPipelineService(config=config, repository=repository)
    artifact = check_service.create_artifact(
        CreateArtifactCommand(
            original_filename="policy.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            payload=fixture_paths["format_errors"].read_bytes(),
            ruleset_id="aeos",
            ruleset_version="2026.04",
            user=UserContext.local("tester"),
        )
    )

    review_service = ReviewService(config=config, repository=repository)
    review_service.process_artifact(artifact.artifact_id)
    session = review_service.load_review_session(artifact.artifact_id)
    finding_id = session.review_entries[0].summary_entry.finding_id

    updated = review_service.update_review_state(
        artifact_id=artifact.artifact_id,
        finding_id=finding_id,
        status=ReviewStatus.FALSE_POSITIVE,
        actor="reviewer@example.com",
    )

    assert updated.pending_count == session.pending_count - 1
    target_entry = next(
        entry for entry in updated.review_entries if entry.summary_entry.finding_id == finding_id
    )
    assert target_entry.review_status is ReviewStatus.FALSE_POSITIVE
    assert target_entry.updated_by == "reviewer@example.com"
