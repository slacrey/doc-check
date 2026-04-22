from __future__ import annotations

from pathlib import Path

from docx import Document

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.reports.comment_writer import write_annotated_docx
from doc_check.reports.summary_builder import build_summary_report
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_annotated_docx_output_matches_summary_report(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    evaluation = RuleEngine().evaluate(snapshot, load_rule_pack(Path("rulesets/aeos")))
    report = build_summary_report(evaluation)

    output_path = tmp_path / "annotated-format-errors.docx"
    result = write_annotated_docx(
        source_path=fixture_paths["format_errors"],
        findings=evaluation.findings,
        output_path=output_path,
    )

    annotated = Document(output_path)

    assert report.total_findings == 17
    assert len(annotated.comments) == result.commented_count
    assert result.commented_count == sum(1 for entry in report.entries if entry.target.value == "commentable")
    assert result.summary_only_count == sum(1 for entry in report.entries if entry.target.value == "summary_only")
    assert any("规则：" in comment.text for comment in annotated.comments)
