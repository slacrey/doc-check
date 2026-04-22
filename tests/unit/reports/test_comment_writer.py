from __future__ import annotations

from pathlib import Path

from docx import Document

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.reports.comment_writer import write_annotated_docx
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_comment_writer_writes_comments_only_for_commentable_findings(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    evaluation = RuleEngine().evaluate(snapshot, load_rule_pack(Path("rulesets/aeos")))

    output_path = tmp_path / "annotated.docx"
    result = write_annotated_docx(
        source_path=fixture_paths["format_errors"],
        findings=evaluation.findings,
        output_path=output_path,
    )

    annotated = Document(output_path)

    assert output_path.exists()
    assert len(annotated.comments) == result.commented_count
    assert result.commented_count == 9
    assert result.summary_only_count == 8
    assert result.skipped_count == 0
    assert any("正文宜统一使用 3 号仿宋体。" in comment.text for comment in annotated.comments)
    assert all("页眉" not in comment.text for comment in annotated.comments)
