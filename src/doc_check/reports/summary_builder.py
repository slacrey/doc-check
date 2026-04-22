from __future__ import annotations

from datetime import datetime, timezone

from doc_check.domain.findings import (
    SummaryReport,
    counts_from_evaluation,
    report_entry_from_finding,
)
from doc_check.domain.rules import RuleEvaluation


def build_summary_report(
    evaluation: RuleEvaluation,
    *,
    generated_at: datetime | None = None,
) -> SummaryReport:
    timestamp = generated_at or datetime.now(timezone.utc)
    severity_counts, category_counts = counts_from_evaluation(evaluation)

    return SummaryReport(
        ruleset_id=evaluation.ruleset_id,
        ruleset_version=evaluation.ruleset_version,
        generated_at=timestamp,
        total_findings=len(evaluation.findings),
        counts_by_severity=severity_counts,
        counts_by_category=category_counts,
        entries=tuple(report_entry_from_finding(finding) for finding in evaluation.findings),
    )
