from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from doc_check.domain.rules import RuleEvaluation, RuleFinding


class SummaryEntryTarget(StrEnum):
    COMMENTABLE = "commentable"
    SUMMARY_ONLY = "summary_only"


class ReviewStatus(StrEnum):
    OPEN = "open"
    FALSE_POSITIVE = "false_positive"
    ACCEPTABLE_EXCEPTION = "acceptable_exception"


@dataclass(frozen=True, slots=True)
class SummaryEntry:
    finding_id: str
    rule_id: str
    category: str
    severity: str
    disposition: str
    message: str
    location_label: str
    evidence: str | None
    suggestion: str | None
    target: SummaryEntryTarget


@dataclass(frozen=True, slots=True)
class SummaryReport:
    ruleset_id: str
    ruleset_version: str
    generated_at: datetime
    total_findings: int
    counts_by_severity: dict[str, int]
    counts_by_category: dict[str, int]
    entries: tuple[SummaryEntry, ...]


@dataclass(frozen=True, slots=True)
class ReviewState:
    finding_id: str
    status: ReviewStatus
    updated_by: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewEntry:
    summary_entry: SummaryEntry
    review_status: ReviewStatus
    updated_by: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReviewSession:
    artifact_id: str
    summary_report: SummaryReport
    review_entries: tuple[ReviewEntry, ...]
    pending_count: int
    annotated_download_path: Path | None


@dataclass(frozen=True, slots=True)
class CommentWriteResult:
    output_path: Path
    commented_findings: tuple[RuleFinding, ...]
    summary_only_findings: tuple[RuleFinding, ...]
    skipped_findings: tuple[RuleFinding, ...]

    @property
    def commented_count(self) -> int:
        return len(self.commented_findings)

    @property
    def summary_only_count(self) -> int:
        return len(self.summary_only_findings)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_findings)


def target_for_finding(finding: RuleFinding) -> SummaryEntryTarget:
    if finding.location is not None and finding.location.anchor_kind.value == "commentable":
        return SummaryEntryTarget.COMMENTABLE
    return SummaryEntryTarget.SUMMARY_ONLY


def report_entry_from_finding(finding: RuleFinding) -> SummaryEntry:
    return SummaryEntry(
        finding_id=finding.finding_id,
        rule_id=finding.rule_id,
        category=finding.category,
        severity=finding.severity.value,
        disposition=finding.disposition.value,
        message=finding.message,
        location_label=finding.location_label,
        evidence=finding.evidence,
        suggestion=finding.suggestion,
        target=target_for_finding(finding),
    )


def counts_from_evaluation(evaluation: RuleEvaluation) -> tuple[dict[str, int], dict[str, int]]:
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    for finding in evaluation.findings:
        severity_counts[finding.severity.value] = severity_counts.get(finding.severity.value, 0) + 1
        category_counts[finding.category] = category_counts.get(finding.category, 0) + 1

    return severity_counts, category_counts
