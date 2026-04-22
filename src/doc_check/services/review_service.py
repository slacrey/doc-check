from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from doc_check.config import AppConfig
from doc_check.domain.documents import ArtifactRecord, ArtifactStatus
from doc_check.domain.findings import (
    ReviewEntry,
    ReviewSession,
    ReviewState,
    ReviewStatus,
    SummaryEntry,
    SummaryReport,
    SummaryEntryTarget,
)
from doc_check.domain.rules import RuleEvaluation, RuleFinding
from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.persistence.repositories import ArtifactRepository
from doc_check.reports.comment_writer import write_annotated_docx
from doc_check.reports.summary_builder import build_summary_report
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack


class ReviewServiceError(ValueError):
    """Base error for review service operations."""


class ReviewNotFoundError(ReviewServiceError):
    """Raised when an artifact review session cannot be found."""


class ReviewExpiredError(ReviewServiceError):
    """Raised when an artifact has been cleaned up and is no longer available."""


class ReviewService:
    def __init__(
        self,
        *,
        config: AppConfig,
        repository: ArtifactRepository,
        rule_engine: RuleEngine | None = None,
    ) -> None:
        self._config = config
        self._repository = repository
        self._rule_engine = rule_engine or RuleEngine()

    def process_artifact(self, artifact_id: str) -> ArtifactRecord:
        artifact = self._require_artifact(artifact_id)
        artifact_dir = artifact.storage_path.parent
        review_states_path = artifact_dir / "review_states.json"
        findings_path = artifact_dir / "findings.json"
        summary_path = artifact_dir / "summary.json"
        annotated_path = artifact_dir / "annotated.docx"

        processing_record = replace(artifact, status=ArtifactStatus.PROCESSING)
        self._repository.update(processing_record)

        try:
            snapshot = read_docx_snapshot(artifact.storage_path)
            rule_pack = load_rule_pack(self._config.rulesets_dir / artifact.ruleset_id)
            evaluation = self._rule_engine.evaluate(snapshot, rule_pack)
            summary_report = build_summary_report(evaluation)
            comment_result = write_annotated_docx(
                source_path=artifact.storage_path,
                findings=evaluation.findings,
                output_path=annotated_path,
            )

            self._write_json(findings_path, _serialize_findings(evaluation.findings))
            self._write_json(review_states_path, {})
            self._write_json(
                summary_path,
                _build_review_summary_payload(
                    summary_report=summary_report,
                    entries=summary_report.entries,
                    review_states={},
                ),
            )

            completed_record = replace(
                processing_record,
                status=ArtifactStatus.COMPLETED,
                ruleset_version=rule_pack.version,
                annotated_path=comment_result.output_path,
                summary_path=summary_path,
            )
            return self._repository.update(completed_record)
        except Exception:
            failed_record = replace(processing_record, status=ArtifactStatus.FAILED)
            self._repository.update(failed_record)
            raise

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        return self._require_artifact(artifact_id)

    def load_review_session(self, artifact_id: str) -> ReviewSession:
        artifact = self._require_artifact(artifact_id)
        if artifact.status is ArtifactStatus.EXPIRED:
            raise ReviewExpiredError(f"Artifact {artifact_id} has expired")

        artifact_dir = artifact.storage_path.parent
        findings_path = artifact_dir / "findings.json"
        review_states_path = artifact_dir / "review_states.json"
        summary_path = artifact.summary_path or (artifact_dir / "summary.json")

        if not findings_path.exists():
            raise ReviewServiceError(f"Artifact {artifact_id} has not been processed yet")

        entries = tuple(_deserialize_summary_entry(item) for item in self._read_json(findings_path))
        states = self._load_review_states(review_states_path)
        review_entries = tuple(_merge_review_entries(entries, states))
        if summary_path.exists():
            summary_report, pending_count = _deserialize_summary_report(summary_path, entries)
        else:
            summary_report = build_summary_report(
                RuleEvaluation(
                    ruleset_id=artifact.ruleset_id,
                    ruleset_version=artifact.ruleset_version,
                    findings=tuple(_summary_entry_to_finding_stub(entry) for entry in entries),
                )
            )
            pending_count = sum(1 for entry in review_entries if entry.review_status is ReviewStatus.OPEN)

        return ReviewSession(
            artifact_id=artifact.artifact_id,
            summary_report=summary_report,
            review_entries=review_entries,
            pending_count=pending_count,
            annotated_download_path=artifact.annotated_path,
        )

    def update_review_state(
        self,
        *,
        artifact_id: str,
        finding_id: str,
        status: ReviewStatus,
        actor: str,
        updated_at: datetime | None = None,
    ) -> ReviewSession:
        artifact = self._require_artifact(artifact_id)
        artifact_dir = artifact.storage_path.parent
        findings_path = artifact_dir / "findings.json"
        review_states_path = artifact_dir / "review_states.json"
        summary_path = artifact.summary_path or (artifact_dir / "summary.json")

        entries = tuple(_deserialize_summary_entry(item) for item in self._read_json(findings_path))
        if finding_id not in {entry.finding_id for entry in entries}:
            raise ReviewServiceError(f"Unknown finding_id: {finding_id}")

        states = self._load_review_states(review_states_path)
        timestamp = updated_at or datetime.now(timezone.utc)

        if status is ReviewStatus.OPEN:
            states.pop(finding_id, None)
        else:
            states[finding_id] = ReviewState(
                finding_id=finding_id,
                status=status,
                updated_by=actor,
                updated_at=timestamp,
            )

        self._write_json(
            review_states_path,
            {finding_id: _serialize_review_state(state) for finding_id, state in states.items()},
        )

        summary_report = build_summary_report(
            RuleEvaluation(
                ruleset_id=artifact.ruleset_id,
                ruleset_version=artifact.ruleset_version,
                findings=tuple(_summary_entry_to_finding_stub(entry) for entry in entries),
            )
        )
        self._write_json(
            summary_path,
            _build_review_summary_payload(
                summary_report=summary_report,
                entries=entries,
                review_states=states,
            ),
        )

        return self.load_review_session(artifact_id)

    def cleanup_expired_artifacts(self, *, as_of: datetime | None = None) -> list[str]:
        expired_artifacts = self._repository.list_expired(as_of=as_of)
        cleaned_ids: list[str] = []

        for artifact in expired_artifacts:
            artifact_dir = artifact.storage_path.parent
            shutil.rmtree(artifact_dir, ignore_errors=True)

            updated_record = replace(
                artifact,
                status=ArtifactStatus.EXPIRED,
                annotated_path=None,
                summary_path=None,
            )
            self._repository.update(updated_record)
            cleaned_ids.append(artifact.artifact_id)

        return cleaned_ids

    def _load_review_states(self, path: Path) -> dict[str, ReviewState]:
        if not path.exists():
            return {}
        payload = self._read_json(path)
        return {
            finding_id: _deserialize_review_state(item)
            for finding_id, item in payload.items()
        }

    def _require_artifact(self, artifact_id: str) -> ArtifactRecord:
        artifact = self._repository.get(artifact_id)
        if artifact is None:
            raise ReviewNotFoundError(f"Artifact {artifact_id} was not found")
        return artifact

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))


def _serialize_findings(findings: tuple[RuleFinding, ...]) -> list[dict[str, object]]:
    return [_serialize_summary_entry_from_finding(finding) for finding in findings]


def _serialize_summary_entry_from_finding(finding: RuleFinding) -> dict[str, object]:
    target = SummaryEntryTarget.COMMENTABLE
    if finding.location is None or finding.location.anchor_kind.value != "commentable":
        target = SummaryEntryTarget.SUMMARY_ONLY

    return {
        "finding_id": finding.finding_id,
        "rule_id": finding.rule_id,
        "category": finding.category,
        "severity": finding.severity.value,
        "disposition": finding.disposition.value,
        "message": finding.message,
        "location_label": finding.location_label,
        "evidence": finding.evidence,
        "suggestion": finding.suggestion,
        "target": target.value,
    }


def _serialize_review_state(review_state: ReviewState) -> dict[str, str]:
    return {
        "finding_id": review_state.finding_id,
        "status": review_state.status.value,
        "updated_by": review_state.updated_by,
        "updated_at": review_state.updated_at.isoformat(),
    }


def _deserialize_review_state(payload: dict[str, str]) -> ReviewState:
    return ReviewState(
        finding_id=payload["finding_id"],
        status=ReviewStatus(payload["status"]),
        updated_by=payload["updated_by"],
        updated_at=datetime.fromisoformat(payload["updated_at"]),
    )


def _deserialize_summary_entry(payload: dict[str, object]) -> SummaryEntry:
    return SummaryEntry(
        finding_id=str(payload["finding_id"]),
        rule_id=str(payload["rule_id"]),
        category=str(payload["category"]),
        severity=str(payload["severity"]),
        disposition=str(payload["disposition"]),
        message=str(payload["message"]),
        location_label=str(payload["location_label"]),
        evidence=str(payload["evidence"]) if payload.get("evidence") is not None else None,
        suggestion=str(payload["suggestion"]) if payload.get("suggestion") is not None else None,
        target=SummaryEntryTarget(str(payload["target"])),
    )


def _merge_review_entries(
    entries: tuple[SummaryEntry, ...],
    states: dict[str, ReviewState],
):
    for entry in entries:
        state = states.get(entry.finding_id)
        if state is None:
            yield ReviewEntry(summary_entry=entry, review_status=ReviewStatus.OPEN)
            continue

        yield ReviewEntry(
            summary_entry=entry,
            review_status=state.status,
            updated_by=state.updated_by,
            updated_at=state.updated_at,
        )


def _build_review_summary_payload(
    *,
    summary_report,
    entries: tuple[SummaryEntry, ...],
    review_states: dict[str, ReviewState],
) -> dict[str, object]:
    review_entries = list(_merge_review_entries(entries, review_states))
    counts_by_review_status: dict[str, int] = {}
    for entry in review_entries:
        counts_by_review_status[entry.review_status.value] = (
            counts_by_review_status.get(entry.review_status.value, 0) + 1
        )

    return {
        "ruleset_id": summary_report.ruleset_id,
        "ruleset_version": summary_report.ruleset_version,
        "generated_at": summary_report.generated_at.isoformat(),
        "total_findings": summary_report.total_findings,
        "pending_count": sum(1 for entry in review_entries if entry.review_status is ReviewStatus.OPEN),
        "counts_by_severity": summary_report.counts_by_severity,
        "counts_by_category": summary_report.counts_by_category,
        "counts_by_review_status": counts_by_review_status,
        "entries": [
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
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            }
            for entry in review_entries
        ],
    }


def _deserialize_summary_report(
    path: Path,
    entries: tuple[SummaryEntry, ...],
) -> tuple[SummaryReport, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = SummaryReport(
        ruleset_id=str(payload["ruleset_id"]),
        ruleset_version=str(payload["ruleset_version"]),
        generated_at=datetime.fromisoformat(str(payload["generated_at"])),
        total_findings=int(payload["total_findings"]),
        counts_by_severity={str(key): int(value) for key, value in payload["counts_by_severity"].items()},
        counts_by_category={str(key): int(value) for key, value in payload["counts_by_category"].items()},
        entries=entries,
    )
    pending_count = int(payload.get("pending_count", report.total_findings))
    return report, pending_count


def _summary_entry_to_finding_stub(entry: SummaryEntry) -> RuleFinding:
    from doc_check.domain.rules import FindingDisposition, FindingSeverity

    return RuleFinding(
        rule_id=entry.rule_id,
        ruleset_id="stub",
        ruleset_version="stub",
        category=entry.category,
        severity=FindingSeverity(entry.severity),
        disposition=FindingDisposition(entry.disposition),
        message=entry.message,
        location=None,
        location_label=entry.location_label,
        evidence=entry.evidence,
        suggestion=entry.suggestion,
    )
