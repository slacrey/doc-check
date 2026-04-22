from __future__ import annotations

from doc_check.domain.documents import CreateArtifactCommand, UserContext
from doc_check.persistence.repositories import ArtifactRepository
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import CheckPipelineService
from doc_check.services.review_service import ReviewService
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_check_execution_service_runs_single_check_and_returns_serialized_summary(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    config.ensure_directories()
    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    execution_service = CheckExecutionService(
        check_service=CheckPipelineService(config=config, repository=repository),
        review_service=ReviewService(config=config, repository=repository),
    )

    result = execution_service.run_check(
        CreateArtifactCommand(
            original_filename="policy.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            payload=fixture_paths["format_errors"].read_bytes(),
            ruleset_id="aeos",
            ruleset_version="2026.05",
            user=UserContext.local("tester"),
        )
    )

    payload = result.as_public_dict()

    assert result.artifact.status.value == "completed"
    assert result.review_session.summary_report.total_findings == 17
    assert payload["artifact"]["artifact_id"] == result.artifact.artifact_id
    assert payload["summary"]["total_findings"] == 17
    assert payload["summary"]["pending_count"] == 17
    assert len(payload["findings"]) == 17
