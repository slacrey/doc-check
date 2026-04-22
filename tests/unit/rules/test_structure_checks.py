from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.rules.checks.structure import run_structure_checks
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_structure_checks_flag_missing_sections_and_story_text(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    rule_pack = load_rule_pack(Path("rulesets/aeos"))

    findings = run_structure_checks(snapshot, rule_pack)
    rule_ids = {finding.rule_id for finding in findings}

    assert "structure.required-heading.purpose" in rule_ids
    assert "structure.toc.required" in rule_ids
    assert "structure.header.expected-text" in rule_ids
    assert "structure.footer.expected-text" in rule_ids
