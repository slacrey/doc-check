from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.reports.summary_builder import build_summary_report
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_summary_builder_counts_findings_and_preserves_targets(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    evaluation = RuleEngine().evaluate(snapshot, load_rule_pack(Path("rulesets/aeos")))

    report = build_summary_report(
        evaluation,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    assert report.ruleset_id == "aeos"
    assert report.total_findings == len(evaluation.findings)
    assert report.counts_by_category == {
        "punctuation": 1,
        "structure": 4,
        "style": 2,
        "terminology": 2,
    }
    assert report.counts_by_severity == {"error": 4, "warning": 5}
    assert any(entry.target.value == "commentable" for entry in report.entries)
    assert any(entry.target.value == "summary_only" for entry in report.entries)
