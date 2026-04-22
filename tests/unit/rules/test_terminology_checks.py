from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.rules.checks.terminology import run_terminology_checks
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_terminology_checks_detect_preferred_and_banned_terms(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    snapshot = read_docx_snapshot(fixture_paths["format_errors"])
    rule_pack = load_rule_pack(Path("rulesets/aeos"))

    findings = run_terminology_checks(snapshot, rule_pack)
    rule_ids = {finding.rule_id for finding in findings}

    assert "terminology.preferred.network-info-security" in rule_ids
    assert "terminology.banned.blacklist" in rule_ids
