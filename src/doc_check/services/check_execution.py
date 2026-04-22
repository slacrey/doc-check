from __future__ import annotations

from dataclasses import dataclass

from doc_check.domain.documents import ArtifactRecord, CreateArtifactCommand
from doc_check.domain.findings import ReviewSession, ReviewStatus
from doc_check.services.check_pipeline import CheckPipelineService
from doc_check.services.review_service import ReviewService


@dataclass(frozen=True, slots=True)
class CheckExecutionResult:
    artifact: ArtifactRecord
    review_session: ReviewSession

    @property
    def artifact_id(self) -> str:
        return self.artifact.artifact_id

    @property
    def false_positive_count(self) -> int:
        return sum(
            1
            for entry in self.review_session.review_entries
            if entry.review_status is ReviewStatus.FALSE_POSITIVE
        )

    @property
    def acceptable_exception_count(self) -> int:
        return sum(
            1
            for entry in self.review_session.review_entries
            if entry.review_status is ReviewStatus.ACCEPTABLE_EXCEPTION
        )

    def as_public_dict(self) -> dict[str, object]:
        report = self.review_session.summary_report
        return {
            "artifact": self.artifact.as_public_dict(),
            "summary": {
                "ruleset_id": report.ruleset_id,
                "ruleset_version": report.ruleset_version,
                "generated_at": report.generated_at.isoformat(),
                "total_findings": report.total_findings,
                "pending_count": self.review_session.pending_count,
                "false_positive_count": self.false_positive_count,
                "acceptable_exception_count": self.acceptable_exception_count,
                "counts_by_severity": report.counts_by_severity,
                "counts_by_category": report.counts_by_category,
            },
            "findings": [
                {
                    "finding_id": entry.summary_entry.finding_id,
                    "rule_id": entry.summary_entry.rule_id,
                    "category": entry.summary_entry.category,
                    "severity": entry.summary_entry.severity,
                    "disposition": entry.summary_entry.disposition,
                    "message": entry.summary_entry.message,
                    "location_label": entry.summary_entry.location_label,
                    "evidence": entry.summary_entry.evidence,
                    "suggestion": entry.summary_entry.suggestion,
                    "target": entry.summary_entry.target.value,
                    "review_status": entry.review_status.value,
                    "updated_by": entry.updated_by,
                    "updated_at": (
                        entry.updated_at.isoformat() if entry.updated_at is not None else None
                    ),
                }
                for entry in self.review_session.review_entries
            ],
        }


class CheckExecutionService:
    def __init__(
        self,
        *,
        check_service: CheckPipelineService,
        review_service: ReviewService,
    ) -> None:
        self._check_service = check_service
        self._review_service = review_service

    def run_check(self, command: CreateArtifactCommand) -> CheckExecutionResult:
        artifact = self._check_service.create_artifact(command)
        completed_artifact = self._review_service.process_artifact(artifact.artifact_id)
        review_session = self._review_service.load_review_session(artifact.artifact_id)
        return CheckExecutionResult(
            artifact=completed_artifact,
            review_session=review_session,
        )
