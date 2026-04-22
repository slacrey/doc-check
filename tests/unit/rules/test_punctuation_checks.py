from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.rules.checks.punctuation import run_punctuation_checks
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_punctuation_checks_detect_ascii_comma_in_cjk_text(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    rule_pack = load_rule_pack(Path("rulesets/aeos"))

    findings = run_punctuation_checks(snapshot, rule_pack)

    assert [finding.rule_id for finding in findings] == ["punctuation.ascii-comma-cjk"]
